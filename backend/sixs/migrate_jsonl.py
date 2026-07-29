#!/usr/bin/env python3
"""Migrate the append-only JSONL archive into the 6S capture tables.

READ-ONLY with respect to the archive. This script never writes to, moves,
renames or truncates corpus.jsonl / ratings.jsonl. Those files remain the
system of record until the tables are proven.

Idempotent: every row carries a source_ref and inserts use
ON CONFLICT DO NOTHING, so re-running imports nothing new.

Record shapes, read from training_backend.py rather than assumed
    corpus.jsonl   {id, track, block, value, learner, ts}
    ratings.jsonl  {response_id, rater, level, ts}

Mapping decisions, and why
--------------------------
* One corpus record becomes one `submissions` row. Grouping by learner+track
  was the alternative, but ratings are keyed to an individual response id — a
  1:1 mapping is the only one that keeps human_grades.submission_id honest.
  Grouping stays available later via user_ref/track/created_at.

* A legacy rating is a single ordinal on the cordaie 0-3 scale
  (0-missing / 1-vague / 2-specific / 3-falsifiable). It is NOT a 6x3 matrix.
  Rather than fabricate a matrix shape, it is stored as

      {"kind": "legacy_cordaie_ordinal", "scale": [...], "level": "2-specific",
       "block": "m1e0", "matrix": null}

  with matrix null. Anything reading grade_matrix must branch on "kind"; a
  legacy ordinal cannot be compared cell-for-cell against a 6S matrix without
  a documented conversion, and inventing one here would be inventing data.

* Corpus records are NOT scored during migration. The cordaie block ids
  (m0e0, m1e1, ...) have no mapping to 6S sub-item names
  (S11_intent_statement, ...). Retro-scoring the archive needs that mapping
  built first. See --report for how many rows are affected.

Usage
    CORDIA_PG_DSN=... python3 backend/sixs/migrate_jsonl.py --report
    CORDIA_PG_DSN=... python3 backend/sixs/migrate_jsonl.py --apply
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixs import store                             # noqa: E402
from sixs.aie_map import registry_for             # noqa: E402

DATA = os.environ.get("CORDIA_CORPUS_DIR", "/var/lib/cordia/corpus")
CORPUS = os.path.join(DATA, "corpus.jsonl")
RATINGS = os.path.join(DATA, "ratings.jsonl")

RUBRIC_LEVELS = ["0-missing", "1-vague", "2-specific", "3-falsifiable"]


def read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        print(f"  ! not found: {path}")
        return []
    rows, bad = [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                bad += 1
    if bad:
        print(f"  ! {bad} unparseable line(s) skipped in {os.path.basename(path)}")
    return rows


def _ts(v) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(float(v), dt.timezone.utc)
    except Exception:
        return None


def report() -> dict:
    """Row counts and validation readiness. Touches the archive read-only."""
    corpus = read_jsonl(CORPUS)
    ratings = read_jsonl(RATINGS)

    per_response: dict[str, set[str]] = {}
    for r in ratings:
        rid = str(r.get("response_id", ""))
        rater = str(r.get("rater", ""))
        if rid and rater:
            per_response.setdefault(rid, set()).add(rater)

    multi = {rid: raters for rid, raters in per_response.items() if len(raters) >= 2}
    corpus_ids = {str(c.get("id", "")) for c in corpus}
    orphan = [rid for rid in per_response if rid not in corpus_ids]

    learners = Counter(str(c.get("learner", "")) for c in corpus)
    tracks = Counter(str(c.get("track", "")) for c in corpus)
    blocks = Counter(str(c.get("block", "")) for c in corpus)
    levels = Counter(str(r.get("level", "")) for r in ratings)

    out = {
        "corpus_records": len(corpus),
        "rating_records": len(ratings),
        "responses_with_any_rating": len(per_response),
        "responses_with_2plus_independent_raters": len(multi),
        "orphan_ratings_no_matching_response": len(orphan),
        "distinct_learners": len(learners),
        "distinct_tracks": len(tracks),
        "distinct_blocks": len(blocks),
        "rating_level_distribution": dict(levels),
        "top_tracks": dict(tracks.most_common(8)),
        "blocks_mappable_to_6s_items": sorted(
            b for (t, b) in {(str(c.get("track","")), str(c.get("block",""))) for c in corpus}
            if (lambda reg: reg is not None and b in reg.item_map)(registry_for(t))
        ),
        "blocks_not_mappable_to_6s_items": len({
            (t, b) for (t, b) in {(str(c.get("track","")), str(c.get("block",""))) for c in corpus}
            if (lambda reg: reg is None or b not in reg.item_map)(registry_for(t))
        }),
    }
    return out


def apply() -> dict:
    corpus = read_jsonl(CORPUS)
    ratings = read_jsonl(RATINGS)

    store.init_schema()

    # block lookup built once — the archive can be large, and scanning it per
    # rating would make this quadratic
    block_of = {str(rec.get("id", "")): str(rec.get("block", "")) for rec in corpus}

    # corpus -> submissions, keyed by the original record id
    id_map: dict[str, int] = {}
    inserted_subs = skipped_subs = 0
    for rec in corpus:
        src = str(rec.get("id", "")).strip()
        if not src:
            continue
        learner = str(rec.get("learner") or "anon")
        sub_id = store.insert_submission(
            user_ref=learner,
            payload=rec,                       # the whole raw record, nothing dropped
            source_ref=f"corpus:{src}",
            created_at=_ts(rec.get("ts")),
        )
        if sub_id is None:
            existing = store.get_submission_id_by_source(f"corpus:{src}")
            if existing is not None:
                id_map[src] = existing
            skipped_subs += 1
        else:
            id_map[src] = sub_id
            inserted_subs += 1

    # ratings -> human_grades
    inserted_grades = skipped_grades = orphan_grades = 0
    for r in ratings:
        rid = str(r.get("response_id", "")).strip()
        rater = str(r.get("rater", "")).strip()
        level = str(r.get("level", "")).strip()
        if not (rid and rater):
            continue
        sub_id = id_map.get(rid)
        if sub_id is None:
            orphan_grades += 1
            continue
        block = block_of.get(rid, "")
        grade = {
            "kind": "legacy_cordaie_ordinal",
            "scale": RUBRIC_LEVELS,
            "level": level or None,
            "block": block or None,
            "matrix": None,      # explicitly not a 6x3 matrix — do not infer one
        }
        gid = store.insert_human_grade(
            submission_id=sub_id,
            grader_ref=f"legacy-rater-{rater}",
            grade_matrix=grade,
            notes="migrated from ratings.jsonl; ordinal scale, not a 6S matrix",
            source_ref=f"rating:{rid}:{rater}:{r.get('ts')}",
            graded_at=_ts(r.get("ts")),
        )
        if gid is None:
            skipped_grades += 1
        else:
            inserted_grades += 1

    return {
        "submissions_inserted": inserted_subs,
        "submissions_already_present": skipped_subs,
        "grades_inserted": inserted_grades,
        "grades_already_present": skipped_grades,
        "grades_orphaned_no_matching_submission": orphan_grades,
        "table_counts": store.counts(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true",
                   help="row counts only; touches no database, writes nothing")
    g.add_argument("--apply", action="store_true",
                   help="insert into Postgres (idempotent)")
    args = ap.parse_args()

    print(f"corpus dir: {DATA}\n")
    if args.report:
        print(json.dumps(report(), indent=2))
        return 0

    print(json.dumps(report(), indent=2))
    print("\napplying...\n")
    print(json.dumps(apply(), indent=2, default=str))
    print("\nArchive untouched — corpus.jsonl and ratings.jsonl were opened read-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
