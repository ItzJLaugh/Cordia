#!/usr/bin/env python3
"""Shadow scoring hook — the seam between the live exam and the 6S capture layer.

Design rule, and the reason this module exists at all: **the learner path must
never get slower, and must never break, because of 6S.** cordaie_scoring.py is
authoritative; this is a passive observer sitting behind it.

That rule is enforced structurally, not by convention:

  * ``submit()`` only puts a job on a bounded queue and returns. No scoring, no
    database, no file reads happen on the request thread — zero added latency.
  * The queue has a maximum size. Under load, jobs are dropped and counted
    rather than blocking a learner's submission.
  * A single daemon worker does the work, and its top-level handler catches
    BaseException. Nothing escapes into the HTTP handler.
  * Every import that could fail on a misconfigured box (psycopg2, missing
    DSN) is deferred and guarded, so importing this module can never stop
    training_backend from starting.

If any of it is broken or unconfigured, the exam keeps working and
``status()`` reports why.
"""

from __future__ import annotations

import os
import queue
import threading
import time
import traceback
from typing import Any, Callable

from .aie_map import latest_by_block, registry_for

_QUEUE_MAX = int(os.environ.get("CORDIA_6S_QUEUE_MAX", "256"))
_ENABLED = os.environ.get("CORDIA_6S_SHADOW", "1") != "0"

_q: "queue.Queue[tuple[dict, Callable[[], list[dict]]]]" = queue.Queue(maxsize=_QUEUE_MAX)
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()

_stats: dict[str, Any] = {
    "enabled": _ENABLED,
    "queued": 0,
    "dropped_queue_full": 0,
    "scored": 0,
    "written": 0,
    "skipped_unmapped_track": 0,
    "errors": 0,
    "last_error": None,
    "last_error_at": None,
    "last_written_at": None,
    "worker_alive": False,
}
_stats_lock = threading.Lock()


def _bump(key: str, n: int = 1) -> None:
    with _stats_lock:
        _stats[key] = _stats.get(key, 0) + n


def _note_error(exc: BaseException) -> None:
    with _stats_lock:
        _stats["errors"] = _stats.get("errors", 0) + 1
        # message only — never a full traceback into a status endpoint
        _stats["last_error"] = f"{type(exc).__name__}: {exc}"[:300]
        _stats["last_error_at"] = time.time()


def configured() -> bool:
    """True when a database is actually reachable-in-principle (DSN present)."""
    return bool(os.environ.get("CORDIA_PG_DSN"))


def _process(rec: dict, fetch_rows: Callable[[], list[dict]]) -> None:
    """Score one response event and persist it. Runs on the worker thread only."""
    from . import store                      # deferred: psycopg2 import lives here

    track = rec.get("track")
    registry = registry_for(track)
    if registry is None:
        _bump("skipped_unmapped_track")
        return

    # The submission row is the single raw response record — 1:1 with
    # corpus.jsonl, which is what keeps migrate_jsonl.py and live capture
    # consistent with each other.
    src = rec.get("id")
    sub_id = store.insert_submission(
        user_ref=str(rec.get("learner") or "anon"),
        payload=rec,
        source_ref=f"corpus:{src}" if src else None,
    )
    if sub_id is None and src:
        sub_id = store.get_submission_id_by_source(f"corpus:{src}")
    if sub_id is None:
        return

    # The matrix is computed from the learner's latest answer per block, the
    # same set cordaie_scoring uses, so machine and human numbers describe the
    # same body of work rather than drifting apart.
    rows = fetch_rows() or []
    answers = latest_by_block(rows)
    if not answers:
        return

    from .scorer import score_submission
    result = score_submission(answers, registry)
    _bump("scored")

    result["scorer_signals"]["triggered_by_response"] = src
    result["scorer_signals"]["track"] = track
    result["scorer_signals"]["blocks_present"] = sorted(answers)

    store.insert_score(sub_id, result)
    _bump("written")
    with _stats_lock:
        _stats["last_written_at"] = time.time()


def _run() -> None:
    while True:
        try:
            rec, fetch_rows = _q.get()
        except Exception:                      # pragma: no cover
            return
        try:
            _process(rec, fetch_rows)
        except BaseException as exc:           # noqa: BLE001 - nothing may escape
            _note_error(exc)
            if os.environ.get("CORDIA_6S_DEBUG") == "1":
                traceback.print_exc()
        finally:
            try:
                _q.task_done()
            except Exception:
                pass


def _ensure_worker() -> None:
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="sixs-shadow", daemon=True)
            _worker.start()
            with _stats_lock:
                _stats["worker_alive"] = True


def submit(rec: dict, fetch_rows: Callable[[], list[dict]]) -> None:
    """Queue a response for shadow scoring. Returns immediately, never raises.

    `fetch_rows` is called on the worker thread, so any corpus read it does
    costs the learner nothing.
    """
    if not _ENABLED or not configured():
        return
    try:
        _ensure_worker()
        _q.put_nowait((rec, fetch_rows))
        _bump("queued")
    except queue.Full:
        _bump("dropped_queue_full")
    except BaseException as exc:               # noqa: BLE001 - never reach the caller
        _note_error(exc)


def status() -> dict[str, Any]:
    """Snapshot for the ops/status endpoint. Cheap and side-effect free."""
    with _stats_lock:
        out = dict(_stats)
    out["enabled"] = _ENABLED
    out["dsn_configured"] = configured()
    out["queue_depth"] = _q.qsize()
    out["queue_max"] = _QUEUE_MAX
    out["worker_alive"] = bool(_worker and _worker.is_alive())
    try:
        from .aie_map import AIE1_VERSION
        out["rubric_version"] = AIE1_VERSION
    except Exception:
        out["rubric_version"] = None
    out["shadow_mode"] = True
    out["learner_visible"] = False
    return out


def table_counts() -> dict[str, Any]:
    """Row counts, or an error string. Only called by the status endpoint."""
    if not configured():
        return {"error": "CORDIA_PG_DSN not set"}
    try:
        from . import store
        return store.counts()
    except BaseException as exc:                # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"[:200]}
