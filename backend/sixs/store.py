#!/usr/bin/env python3
"""6S capture layer — Postgres schema and access.

DSN comes from CORDIA_PG_DSN, same as cordia_auth.py (see /etc/cordia/cordia.env).
Requires psycopg2, which is already installed on the VPS. Nothing else.

Schema notes
------------
* ``scores.rubric_version`` is NOT NULL with no default. A score whose rubric
  version is unknown cannot be audited or compared across rubric changes, so
  the database refuses to store one.

* Matrices are JSONB. Unmeasured cells are stored as JSON ``null`` and must
  never be coerced to 0 — "not yet measured" and "scored zero" are different
  facts, and conflating them would silently corrupt every later comparison
  against human grades.

* ``final_composite`` is DOUBLE PRECISION rather than NUMERIC so it round-trips
  as a Python float. NUMERIC returns Decimal, which complicates comparison for
  no benefit at this precision.

* ``human_grades`` deliberately has no uniqueness on submission_id alone —
  two independent graders per submission is the validation design.

* Columns beyond the spec: ``submissions.source_ref`` and
  ``human_grades.source_ref`` carry provenance from the JSONL archive and make
  the migration idempotent (re-running it inserts nothing new). Everything the
  spec listed is present unchanged.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

import psycopg2
import psycopg2.extras

_lock = threading.RLock()

DSN = os.environ.get("CORDIA_PG_DSN", "")


def _conn():
    if not DSN:
        raise RuntimeError("CORDIA_PG_DSN not set. Source /etc/cordia/cordia.env.")
    return psycopg2.connect(DSN)


def _J(obj: Any) -> psycopg2.extras.Json:
    """JSONB adapter that preserves None as JSON null."""
    return psycopg2.extras.Json(obj, dumps=json.dumps)


SCHEMA = """
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


def init_schema() -> None:
    """Create tables and indexes if absent. Safe to run repeatedly."""
    with _lock:
        c = _conn()
        try:
            with c, c.cursor() as cur:
                cur.execute(SCHEMA)
        finally:
            c.close()


# ------------------------------------------------------------------ writes
def insert_submission(user_ref: str, payload: dict[str, Any],
                      source_ref: str | None = None,
                      created_at: Any = None) -> int | None:
    """Insert a submission, return its id. None if source_ref already present."""
    with _lock:
        c = _conn()
        try:
            with c, c.cursor() as cur:
                if created_at is None:
                    cur.execute(
                        "INSERT INTO submissions(user_ref, submission_payload, source_ref) "
                        "VALUES(%s,%s,%s) ON CONFLICT (source_ref) DO NOTHING RETURNING id",
                        (user_ref, _J(payload), source_ref))
                else:
                    cur.execute(
                        "INSERT INTO submissions(user_ref, submission_payload, source_ref, created_at) "
                        "VALUES(%s,%s,%s,%s) ON CONFLICT (source_ref) DO NOTHING RETURNING id",
                        (user_ref, _J(payload), source_ref, created_at))
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            c.close()


def insert_score(submission_id: int, result: dict[str, Any]) -> int:
    """Persist a scorer result. Raises if rubric_version is missing."""
    version = result.get("rubric_version")
    if not version:
        raise ValueError("refusing to store a score with no rubric_version")
    with _lock:
        c = _conn()
        try:
            with c, c.cursor() as cur:
                cur.execute(
                    "INSERT INTO scores(submission_id, rubric_version, score_matrix, "
                    "dimension_composites, final_composite, scorer_signals) "
                    "VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
                    (submission_id, version,
                     _J(result["score_matrix"]),
                     _J(result["dimension_composites"]),
                     result.get("final_composite"),
                     _J(result.get("scorer_signals"))))
                return cur.fetchone()[0]
        finally:
            c.close()


def insert_human_grade(submission_id: int, grader_ref: str,
                       grade_matrix: Any, notes: str | None = None,
                       source_ref: str | None = None,
                       graded_at: Any = None) -> int | None:
    """Insert one grader's grade. Multiple graders per submission are expected."""
    with _lock:
        c = _conn()
        try:
            with c, c.cursor() as cur:
                if graded_at is None:
                    cur.execute(
                        "INSERT INTO human_grades(submission_id, grader_ref, grade_matrix, notes, source_ref) "
                        "VALUES(%s,%s,%s,%s,%s) ON CONFLICT (source_ref) DO NOTHING RETURNING id",
                        (submission_id, grader_ref, _J(grade_matrix), notes, source_ref))
                else:
                    cur.execute(
                        "INSERT INTO human_grades(submission_id, grader_ref, grade_matrix, notes, "
                        "source_ref, graded_at) VALUES(%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (source_ref) DO NOTHING RETURNING id",
                        (submission_id, grader_ref, _J(grade_matrix), notes, source_ref, graded_at))
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            c.close()


def insert_outcome(submission_id: int, recommendation_given: Any = None,
                   outcome_worked: bool | None = None,
                   outcome_description: str | None = None) -> int:
    with _lock:
        c = _conn()
        try:
            with c, c.cursor() as cur:
                cur.execute(
                    "INSERT INTO outcomes(submission_id, recommendation_given, "
                    "outcome_worked, outcome_description) VALUES(%s,%s,%s,%s) RETURNING id",
                    (submission_id, _J(recommendation_given) if recommendation_given is not None else None,
                     outcome_worked, outcome_description))
                return cur.fetchone()[0]
        finally:
            c.close()


# ------------------------------------------------------------------- reads
def get_submission(submission_id: int) -> dict[str, Any] | None:
    return _one("SELECT id, created_at, user_ref, submission_payload, source_ref "
                "FROM submissions WHERE id=%s", (submission_id,))


def get_submission_id_by_source(source_ref: str) -> int | None:
    """Resolve a provenance key back to a submission id. Used by the migration
    to stay idempotent without reaching into private helpers."""
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


def counts() -> dict[str, int]:
    out = {}
    for t in ("submissions", "scores", "human_grades", "outcomes"):
        out[t] = _one(f"SELECT COUNT(*) AS n FROM {t}", ())["n"]
    return out


def _one(sql: str, args: tuple) -> dict[str, Any] | None:
    c = _conn()
    try:
        with c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        c.close()


def _all(sql: str, args: tuple) -> list[dict[str, Any]]:
    c = _conn()
    try:
        with c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]
    finally:
        c.close()
