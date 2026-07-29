#!/usr/bin/env python3
"""STEP 1 verification gate.

Inserts a submission, scores it, writes the score row with a rubric_version,
writes a human grade, reads all three back, and proves the score matrix
round-trips through Postgres with its nulls intact and NOT coerced to 0.

Run against a scratch database, never production:

    CORDIA_PG_DSN='postgresql://user:pw@host:5432/cordia_scratch' \\
        python3 backend/sixs/gate_test.py

Exit code 0 = gate passed. Non-zero = do not proceed to STEP 2.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2                                    # noqa: E402
from sixs import store                             # noqa: E402
from sixs.rubric import DIMENSIONS, TIERS          # noqa: E402
from sixs.scorer import score_submission           # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


# A partial submission on purpose: only 3 of the 8 implemented sub-items.
# That guarantees uncovered cells, which is the whole point of the null test.
SAMPLE = {
    "S11_intent_statement": (
        "This agent is specific to Meridian's quarterly partner briefing. It is "
        "not a general assistant and is not for client-facing correspondence."
    ),
    "S31_named_owner": (
        "Dana Reyes owns this workflow and signs off before anything leaves the team."
    ),
    "S32_constraints_list": (
        "Never send externally without review. Under any circumstances, pause and "
        "escalate if the source data is more than 24 hours old."
    ),
}


def main() -> int:
    print("STEP 1 verification gate\n")

    print("[schema]")
    store.init_schema()
    check("init_schema runs", True)
    store.init_schema()
    check("init_schema is idempotent", True)

    print("\n[score]")
    result = score_submission(SAMPLE)
    matrix = result["score_matrix"]
    check("rubric_version present", bool(result.get("rubric_version")), result.get("rubric_version"))
    check("matrix is 6x3",
          len(matrix) == len(DIMENSIONS) and all(len(r) == len(TIERS) for r in matrix),
          f"{len(matrix)}x{len(matrix[0])}")

    measured = [(d, t) for d, row in enumerate(matrix) for t, v in enumerate(row) if v is not None]
    unmeasured = [(d, t) for d, row in enumerate(matrix) for t, v in enumerate(row) if v is None]
    check("some cells measured", len(measured) > 0, f"{len(measured)} measured")
    check("some cells unmeasured (null test is meaningful)",
          len(unmeasured) > 0, f"{len(unmeasured)} null")
    check("no unmeasured cell is 0",
          all(matrix[d][t] is None for d, t in unmeasured))

    print("\n[write]")
    sub_id = store.insert_submission("gate@cordiacode.com", SAMPLE, source_ref=None)
    check("submission written", isinstance(sub_id, int), f"id={sub_id}")
    score_id = store.insert_score(sub_id, result)
    check("score written", isinstance(score_id, int), f"id={score_id}")

    # human grade in the same 6x3 shape, with its own nulls
    grade = [[None for _ in TIERS] for _ in DIMENSIONS]
    grade[0][0] = 80.0
    grade[2][0] = 65.0
    grade[2][1] = 70.0
    g_id = store.insert_human_grade(sub_id, "grader-A", grade, notes="gate test")
    check("human grade written", isinstance(g_id, int), f"id={g_id}")
    g2_id = store.insert_human_grade(sub_id, "grader-B", grade, notes="second grader")
    check("second grader accepted on same submission", isinstance(g2_id, int), f"id={g2_id}")

    print("\n[read back]")
    got_sub = store.get_submission(sub_id)
    check("submission reads back", got_sub is not None)
    check("payload round-trips whole", got_sub["submission_payload"] == SAMPLE)

    scores = store.get_scores(sub_id)
    check("score reads back", len(scores) == 1)
    row = scores[0]
    check("rubric_version non-null on stored row",
          row["rubric_version"] == result["rubric_version"], row["rubric_version"])

    stored = row["score_matrix"]
    check("matrix shape survives",
          len(stored) == len(DIMENSIONS) and all(len(r) == len(TIERS) for r in stored))
    check("MATRIX NULLS INTACT — every unmeasured cell is still null",
          all(stored[d][t] is None for d, t in unmeasured),
          f"{len(unmeasured)} cells")
    check("no unmeasured cell became 0",
          not any(stored[d][t] == 0 for d, t in unmeasured))
    check("measured values survive exactly",
          all(stored[d][t] == matrix[d][t] for d, t in measured))
    check("dimension_composites nulls intact",
          all((row["dimension_composites"][k] is None) == (v is None)
              for k, v in result["dimension_composites"].items()))

    grades = store.get_human_grades(sub_id)
    check("both grades read back", len(grades) == 2, f"{len(grades)} rows")
    check("grade_matrix nulls intact",
          grades[0]["grade_matrix"][1][2] is None)

    print("\n[constraint]")
    try:
        store.insert_score(sub_id, {**result, "rubric_version": None})
        check("score without rubric_version is rejected", False, "it was accepted")
    except (ValueError, psycopg2.Error):
        check("score without rubric_version is rejected", True)

    print("\n[outcomes]")
    o_id = store.insert_outcome(sub_id, recommendation_given=None,
                                outcome_worked=None,
                                outcome_description="not yet recorded")
    check("outcome row writes with null recommendation", isinstance(o_id, int), f"id={o_id}")

    failed = [n for n, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:", ", ".join(failed))
        print("\nGATE: FAIL — do not proceed to STEP 2")
        return 1
    print("\nGATE: PASS")
    print(f"table counts: {store.counts()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
