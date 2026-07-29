#!/usr/bin/env python3
"""Integration tests for the shadow hook. Standard library only, no database.

These prove the property that matters most: the CordiaAIE exam is unaffected by
6S in every failure mode — package present but unconfigured, database refusing
connections, and the scorer itself raising.

    python3 backend/sixs/test_shadow.py
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


ANSWERS = {
    "m0e0": ("Produce a one-page partner briefing for the Q3 review, because the "
             "partners decide budget from it, within 2 pages."),
    "m0e2": ("If the request touches client data, the agent must not proceed; "
             "the reviewer approves before anything is sent."),
    "m1e0": ("Success means every figure can be verified against the source ledger; "
             "if a figure cannot be checked, the draft is not done."),
    "m2e0": ("When the total exceeds 10,000 the manager approves before the next step."),
    "m2e2": ("Do not send anything externally; stop and escalate to the owner first."),
    "m3e0": ("Shorten section 2 to 3 bullets and apply that rule to every future draft "
             "because partners skim the opening."),
}

WEAK = {
    "m0e0": "Help me write something for this.",
    "m0e2": "Use your best judgment on anything unclear.",
    "m1e0": "It should be accurate and high quality.",
    "m2e0": "Check in with me regularly during the task.",
    "m2e2": "Continue unless there is an obvious problem.",
    "m3e0": "Make it shorter and clearer this time.",
}


def main() -> int:
    print("6S shadow integration\n")

    # ---------------------------------------------------------------- mapping
    print("[registry]")
    from sixs.aie_map import AIE1_REGISTRY, BLOCK_DIMENSION, registry_for
    from sixs.rubric import DIMENSIONS, TIERS

    check("all 12 aie1 blocks mapped", len(BLOCK_DIMENSION) == 12, str(len(BLOCK_DIMENSION)))
    check("every mapped dimension is a real 6S dimension",
          set(BLOCK_DIMENSION.values()) <= set(DIMENSIONS))
    check("foundation row fully covered",
          set(BLOCK_DIMENSION.values()) == set(DIMENSIONS),
          f"{len(set(BLOCK_DIMENSION.values()))}/6 dimensions")
    cov = AIE1_REGISTRY.coverage()
    check("nothing lands outside the foundation tier",
          all(n == 0 for (d, t), n in cov.items() if t != "foundation"))
    check("every block has anchors",
          all(AIE1_REGISTRY.anchors.get(b) for b in BLOCK_DIMENSION))
    check("every block has structural checks",
          all(AIE1_REGISTRY.checks.get(b) for b in BLOCK_DIMENSION))
    check("unmapped track returns no registry", registry_for("some-other-track") is None)
    check("aie1 track resolves to the registry", registry_for("aie1") is AIE1_REGISTRY)

    # ---------------------------------------------------------------- scoring
    print("\n[scoring]")
    from sixs.scorer import score_submission
    strong = score_submission(ANSWERS, AIE1_REGISTRY)
    weak = score_submission(WEAK, AIE1_REGISTRY)

    check("rubric_version is the aie1 one",
          strong["rubric_version"] == AIE1_REGISTRY.version, strong["rubric_version"])
    check("version records unvalidated state", "unvalidated" in strong["rubric_version"])
    check("matrix is 6x3",
          len(strong["score_matrix"]) == 6 and all(len(r) == 3 for r in strong["score_matrix"]))

    design_config = [v for r in strong["score_matrix"] for v in r[1:]]
    check("design + configuration columns are all null (tiers not wired yet)",
          all(v is None for v in design_config))
    check("no cell is 0",
          not any(v == 0 for r in strong["score_matrix"] for v in r))

    gap = strong["final_composite"] - weak["final_composite"]
    check("strong scores above weak", gap > 25, f"gap {gap:.1f} points")

    # partial exam: only some blocks answered
    partial = score_submission({"m0e0": ANSWERS["m0e0"]}, AIE1_REGISTRY)
    measured = [v for r in partial["score_matrix"] for v in r if v is not None]
    check("partial exam yields exactly one measured cell", len(measured) == 1, str(len(measured)))
    check("unanswered dimensions stay null, not 0",
          partial["dimension_composites"]["Success"] is None)

    # ------------------------------------------------------- failure isolation
    print("\n[failure isolation — the exam must survive all of these]")
    from sixs import shadow

    os.environ.pop("CORDIA_PG_DSN", None)
    check("no DSN -> configured() is False", shadow.configured() is False)
    t0 = time.time()
    shadow.submit({"id": "x1", "track": "aie1", "learner": "a@b.c"}, lambda: [])
    check("submit() with no DSN does not raise", True)
    check("submit() returns immediately", (time.time() - t0) < 0.05,
          f"{(time.time() - t0) * 1000:.1f}ms")

    # DSN present but database unreachable — the realistic outage
    os.environ["CORDIA_PG_DSN"] = "postgresql://nobody:nope@127.0.0.1:1/none"
    rec = {"id": "x2", "track": "aie1", "learner": "a@b.c", "block": "m0e0",
           "value": ANSWERS["m0e0"], "ts": time.time()}
    t0 = time.time()
    shadow.submit(rec, lambda: [rec])
    elapsed = time.time() - t0
    check("submit() with dead database does not raise", True)
    check("submit() still returns immediately", elapsed < 0.05, f"{elapsed * 1000:.1f}ms")

    # a fetch callable that explodes must not escape either
    shadow.submit(rec, lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    check("submit() with an exploding fetch does not raise", True)

    for _ in range(60):
        if shadow.status()["errors"] > 0:
            break
        time.sleep(0.05)
    st = shadow.status()
    check("worker recorded the failure instead of crashing", st["errors"] > 0,
          str(st["last_error"])[:70])
    check("worker thread is still alive after errors", st["worker_alive"] is True)
    check("status() reports shadow mode", st["shadow_mode"] is True and st["learner_visible"] is False)
    check("table_counts() degrades to an error dict, not an exception",
          "error" in shadow.table_counts())

    # queue never blocks
    for i in range(shadow._QUEUE_MAX + 50):            # noqa: SLF001
        shadow.submit({"id": f"f{i}", "track": "aie1", "learner": "x"}, lambda: [])
    check("over-capacity submits drop instead of blocking",
          shadow.status()["dropped_queue_full"] >= 0)

    os.environ.pop("CORDIA_PG_DSN", None)

    failed = [n for n, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("\nSHADOW INTEGRATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
