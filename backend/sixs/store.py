#!/usr/bin/env python3
"""6S capture layer — schema and access.

PRODUCTION IS POSTGRES. DSN comes from CORDIA_PG_DSN, same as cordia_auth.py
(see /etc/cordia/cordia.env). Requires psycopg2, already installed on the VPS.

A SQLite dialect exists for local development only, selected with
CORDIA_6S_DB=sqlite. It lets the full pipeline be exercised on a laptop with
no server. It is NOT a production option and does not substitute for the
Postgres verification gate: JSONB null handling, TIMESTAMPTZ and concurrent
writers all behave differently, and those are exactly the behaviours the gate
checks. Run backend/sixs/gate_test.py against real Postgres before trusting
any of this in production.

Schema notes
------------
* ``scores.rubric_version`` is NOT NULL with no default. A score whose rubric
  version is unknown cannot be audited or compared across rubric changes, so
  the database refuses to store one.

* Matrices are JSON. Unmeasured cells are stored as null and must never be
  coerced to 0 — "not yet measured" and "scored zero" are different facts, and
  conflating them would silently corrupt every later comparison against human
  grades.

* ``human_grades`` deliberately has no uniqueness on submission_id alone —
  two independent graders per submission is the validation design.

* Columns beyond the spec: ``submissions.source_ref`` and
  ``human_grades.source_ref`` carry provenance from the JSONL archive and make
  the migration idempotent. Everything the spec listed is present unchanged.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

_lock = threading.RLock()

# columns stored as JSON, parsed back on read
_JSON_COLUMNS = {
    "submission_payload", "score_matrix", "dimension_composites",
    "scorer_signals", "grade_matrix", "recommendation_given",
}


def dialect() -> str:
    return "sqlite" if os.environ.get("CORDIA_6S_DB", "").lower() == "sqlite" else "postgres"


def _sqlite_path() -> str:
    return os.environ.get("CORDIA_6S_SQLITE", os.path.join(os.getcwd(), "cordia-6s-dev.sqlite3"))


def _conn():
    if dialect() == "sqlite":
        import sqlite3
        c = sqlite3.connect(_sqlite_path(), timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c
    import psycopg2
    dsn = os.environ.get("CORDIA_PG_DSN", "")
    if not dsn:
        raise RuntimeError("CORDIA_PG_DSN not set. Source /etc/cordia/cordia.env.")
    return psycopg2.connect(dsn)


def _ph() -> str:
    return "?" if dialect() == "sqlite" else "%s"


def _q(sql: str) -> str:
    """Rewrite %s placeholders for the active dialect."""
    return sql.replace("%s", "?") if dialect() == "sqlite" else sql


def _J(obj: Any):
    """JSON adapter that preserves None as JSON null."""
    if dialect() == "sqlite":
        return json.dumps(obj)
    import psycopg2.extras
    return psycopg2.extras.Json(obj, dumps=json.dumps)


def _row_to_dict(row) -> dict[str, Any]:
    d = dict(row)
    if dialect() == "sqlite":
        for k in list(d):
            if k in _JSON_COLUMNS and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except Exception:
                    pass
    return d


SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS submissions(
    id                 BIGSERIAL PRIMARY KEY,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    user_ref           TEXT         NOT NULL,
    submission_payload JSONB        NOT NULL,
    source_ref         TEXT         UNIQUE
);
CREATE INDEX IF NOT EXISTS submissions_user_idx    ON submissions(user_ref);
CREATE INDEX IF NOT EXISTS submissions_created_idx ON submissions(created_at);

CREATE TABLE IF NOT EXISTS scores(
    id                   BIGSERIAL PRIMARY KEY,
    submission_id        BIGINT       NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    rubric_version       TEXT         NOT NULL,
    score_matrix         JSONB        NOT NULL,
    dimension_composites JSONB        NOT NULL,
    final_composite      DOUBLE PRECISION,
    scored_at            TIMESTAMPTZ  NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    scorer_signals       JSONB
);
CREATE INDEX IF NOT EXISTS scores_submission_idx ON scores(submission_id);
CREATE INDEX IF NOT EXISTS scores_version_idx    ON scores(rubric_version);

CREATE TABLE IF NOT EXISTS human_grades(
    id            BIGSERIAL PRIMARY KEY,
    submission_id BIGINT      NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    grader_ref    TEXT        NOT NULL,
    grade_matrix  JSONB       NOT NULL,
    graded_at     TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    notes         TEXT,
    source_ref    TEXT        UNIQUE
);
CREATE INDEX IF NOT EXISTS human_grades_submission_idx ON human_grades(submission_id);
CREATE INDEX IF NOT EXISTS human_grades_grader_idx     ON human_grades(grader_ref);

CREATE TABLE IF NOT EXISTS outcomes(
    id                    BIGSERIAL PRIMARY KEY,
    submission_id         BIGINT      NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    recommendation_given  JSONB,
    outcome_worked        BOOLEAN,
    outcome_description   TEXT,
    recorded_at           TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS outcomes_submission_idx ON outcomes(submission_id);
"""

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS submissions(
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    user_ref           TEXT NOT NULL,
    submission_payload TEXT NOT NULL,
    source_ref         TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS submissions_user_idx    ON submissions(user_ref);
CREATE INDEX IF NOT EXISTS submissions_created_idx ON submissions(created_at);

CREATE TABLE IF NOT EXISTS scores(
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id        INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    rubric_version       TEXT    NOT NULL,
    score_matrix         TEXT    NOT NULL,
    dimension_composites TEXT    NOT NULL,
    final_composite      REAL,
    scored_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    scorer_signals       TEXT
);
CREATE INDEX IF NOT EXISTS scores_submission_idx ON scores(submission_id);
CREATE INDEX IF NOT EXISTS scores_version_idx    ON scores(rubric_version);

CREATE TABLE IF NOT EXISTS human_grades(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    grader_ref    TEXT    NOT NULL,
    grade_matrix  TEXT    NOT NULL,
    graded_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    notes         TEXT,
    source_ref    TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS human_grades_submission_idx ON human_grades(submission_id);
CREATE INDEX IF NOT EXISTS human_grades_grader_idx     ON human_grades(grader_ref);

CREATE TABLE IF NOT EXISTS outcomes(
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id         INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    recommendation_given  TEXT,
    outcome_worked        INTEGER,
    outcome_description   TEXT,
    recorded_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS outcomes_submission_idx ON outcomes(submission_id);
"""


def init_schema() -> None:
    """Create tables and indexes if absent. Safe to run repeatedly."""
    with _lock:
        c = _conn()
        try:
            if dialect() == "sqlite":
                c.executescript(SCHEMA_SQLITE)
                c.commit()
            else:
                with c, c.cursor() as cur:
                    cur.execute(SCHEMA_PG)
        finally:
            c.close()


def _insert(sql: str, args: tuple) -> int | None:
    """Run an INSERT ... RETURNING id, returning the id or None on conflict."""
    with _lock:
        c = _conn()
        try:
            if dialect() == "sqlite":
                cur = c.execute(_q(sql), args)
                row = cur.fetchone()
                c.commit()
                return row[0] if row else None
            with c, c.cursor() as cur:
                cur.execute(sql, args)
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            c.close()


# ------------------------------------------------------------------ writes
def insert_submission(user_ref: str, payload: dict[str, Any],
                      source_ref: str | None = None,
                      created_at: Any = None) -> int | None:
    """Insert a submission, return its id. None if source_ref already present."""
    if created_at is None:
        return _insert(
            "INSERT INTO submissions(user_ref, submission_payload, source_ref) "
            "VALUES(%s,%s,%s) ON CONFLICT (source_ref) DO NOTHING RETURNING id",
            (user_ref, _J(payload), source_ref))
    if dialect() == "sqlite" and hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    return _insert(
        "INSERT INTO submissions(user_ref, submission_payload, source_ref, created_at) "
        "VALUES(%s,%s,%s,%s) ON CONFLICT (source_ref) DO NOTHING RETURNING id",
        (user_ref, _J(payload), source_ref, created_at))


def insert_score(submission_id: int, result: dict[str, Any]) -> int:
    """Persist a scorer result. Raises if rubric_version is missing."""
    version = result.get("rubric_version")
    if not version:
        raise ValueError("refusing to store a score with no rubric_version")
    return _insert(
        "INSERT INTO scores(submission_id, rubric_version, score_matrix, "
        "dimension_composites, final_composite, scorer_signals) "
        "VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
        (submission_id, version, _J(result["score_matrix"]),
         _J(result["dimension_composites"]), result.get("final_composite"),
         _J(result.get("scorer_signals"))))


def insert_human_grade(submission_id: int, grader_ref: str,
                       grade_matrix: Any, notes: str | None = None,
                       source_ref: str | None = None,
                       graded_at: Any = None) -> int | None:
    """Insert one grader's grade. Multiple graders per submission are expected."""
    if graded_at is None:
        return _insert(
            "INSERT INTO human_grades(submission_id, grader_ref, grade_matrix, notes, source_ref) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT (source_ref) DO NOTHING RETURNING id",
            (submission_id, grader_ref, _J(grade_matrix), notes, source_ref))
    if dialect() == "sqlite" and hasattr(graded_at, "isoformat"):
        graded_at = graded_at.isoformat()
    return _insert(
        "INSERT INTO human_grades(submission_id, grader_ref, grade_matrix, notes, "
        "source_ref, graded_at) VALUES(%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (source_ref) DO NOTHING RETURNING id",
        (submission_id, grader_ref, _J(grade_matrix), notes, source_ref, graded_at))


def insert_outcome(submission_id: int, recommendation_given: Any = None,
                   outcome_worked: bool | None = None,
                   outcome_description: str | None = None) -> int:
    return _insert(
        "INSERT INTO outcomes(submission_id, recommendation_given, "
        "outcome_worked, outcome_description) VALUES(%s,%s,%s,%s) RETURNING id",
        (submission_id,
         _J(recommendation_given) if recommendation_given is not None else None,
         outcome_worked, outcome_description))


# ------------------------------------------------------------------- reads
def get_submission(submission_id: int) -> dict[str, Any] | None:
    return _one("SELECT id, created_at, user_ref, submission_payload, source_ref "
                "FROM submissions WHERE id=%s", (submission_id,))


def get_submission_id_by_source(source_ref: str) -> int | None:
    row = _one("SELECT id FROM submissions WHERE source_ref=%s", (source_ref,))
    return row["id"] if row else None


def get_scores(submission_id: int) -> list[dict[str, Any]]:
    return _all("SELECT id, submission_id, rubric_version, score_matrix, dimension_composites, "
                "final_composite, scored_at, scorer_signals FROM scores "
                "WHERE submission_id=%s ORDER BY id", (submission_id,))


def get_human_grades(submission_id: int) -> list[dict[str, Any]]:
    return _all("SELECT id, submission_id, grader_ref, grade_matrix, graded_at, notes, source_ref "
                "FROM human_grades WHERE submission_id=%s ORDER BY id", (submission_id,))


def get_outcomes(submission_id: int) -> list[dict[str, Any]]:
    return _all("SELECT id, submission_id, recommendation_given, outcome_worked, "
                "outcome_description, recorded_at FROM outcomes "
                "WHERE submission_id=%s ORDER BY id", (submission_id,))


def recent_scores(limit: int = 50, learner: str | None = None) -> list[dict[str, Any]]:
    """Most recent 6S scores joined to their submission, newest first.

    Admin-facing read path. These numbers are unvalidated and must not be
    surfaced to a learner as their certification result.
    """
    limit = max(1, min(int(limit), 500))
    sql = ("SELECT s.id AS score_id, s.submission_id, s.rubric_version, s.score_matrix, "
           "s.dimension_composites, s.final_composite, s.scored_at, s.scorer_signals, "
           "sub.user_ref, sub.created_at, sub.source_ref, sub.submission_payload "
           "FROM scores s JOIN submissions sub ON sub.id = s.submission_id ")
    args: tuple = ()
    if learner:
        sql += "WHERE sub.user_ref = %s "
        args = (learner,)
    sql += "ORDER BY s.id DESC LIMIT %s"
    return _all(sql, args + (limit,))


def score_for_learner(learner: str) -> dict[str, Any] | None:
    rows = recent_scores(limit=1, learner=learner)
    return rows[0] if rows else None


def counts() -> dict[str, int]:
    out = {}
    for t in ("submissions", "scores", "human_grades", "outcomes"):
        out[t] = _one(f"SELECT COUNT(*) AS n FROM {t}", ())["n"]
    return out


def _one(sql: str, args: tuple) -> dict[str, Any] | None:
    c = _conn()
    try:
        if dialect() == "sqlite":
            row = c.execute(_q(sql), args).fetchone()
            return _row_to_dict(row) if row else None
        import psycopg2.extras
        with c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        c.close()


def _all(sql: str, args: tuple) -> list[dict[str, Any]]:
    c = _conn()
    try:
        if dialect() == "sqlite":
            return [_row_to_dict(r) for r in c.execute(_q(sql), args).fetchall()]
        import psycopg2.extras
        with c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]
    finally:
        c.close()
