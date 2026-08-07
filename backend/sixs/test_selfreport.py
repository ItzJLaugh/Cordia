#!/usr/bin/env python3
"""Tests for the three self-report parameters and survey-led agent assignment.

Two properties carry most of the weight here:

  1. Nobody is ranked against themselves. A learner scoring 95 across every
     dimension must come back with nothing marked as developing, and one
     scoring 30 across every dimension must come back with nothing marked as
     strong. That is the bug this change exists to remove, and it is the first
     thing to break if someone reintroduces a sort-and-slice.

  2. Oversight comes from the survey, not the exam. The same 6S profile must
     produce different checkpoint policies for different survey answers, and
     an identical one when the survey is absent.

    python3 backend/sixs/test_selfreport.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sixs import agent_manifest as am          # noqa: E402
from sixs import profile_compiler as pc        # noqa: E402
from sixs import selfreport                    # noqa: E402
from surveyor import types as surv_types       # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def profile_at(value):
    """A compiled 6S profile with every dimension measured at `value`."""
    comps = {d: float(value) for d in pc.DIMS}
    matrix = [[float(value), None, None] for _ in pc.DIMS]
    return pc.compile_profile("t@cordiacode.com", rows=[(matrix, comps, float(value), 0)])


def survey(**answers):
    return {"kind": selfreport.SURVEY_KIND, "learner": "t@cordiacode.com",
            "ts": 1.0, "answers": answers}


def modes(manifest):
    return {a["dimension"]: a["mode"] for a in manifest["agents"]}


def gated(manifest):
    return sorted(d for d, m in modes(manifest).items() if m == "active-checkpoint")


def main() -> int:
    print("\nno one is ranked against themselves")
    high, low = profile_at(95.0), profile_at(30.0)
    check("95 everywhere → nothing developing", high["developing_dims"] == [],
          f"got {high['developing_dims']}")
    check("95 everywhere → all six strong", len(high["strong_dims"]) == 6)
    check("30 everywhere → nothing strong", low["strong_dims"] == [],
          f"got {low['strong_dims']}")
    check("30 everywhere → all six developing", len(low["developing_dims"]) == 6)
    check("weak_dims alias still tracks developing_dims",
          low["weak_dims"] == low["developing_dims"])

    print("\nunmeasured is a gap, never a score")
    partial = pc.compile_profile("t@cordiacode.com", rows=[(
        [[80.0, None, None], [None, None, None]] + [[80.0, None, None]] * 4,
        {"Source": 80.0, "Success": None, "Safety": 80.0,
         "Steering": 80.0, "Switch": 80.0, "Sharpen": 80.0}, 80.0, 0)])
    check("unmeasured dimension lands in gap_dims", partial["gap_dims"] == ["Success"],
          f"got {partial['gap_dims']}")
    check("unmeasured dimension is not developing",
          "Success" not in partial["developing_dims"])
    check("its agent runs shadow, not checkpoint",
          modes(am.build_manifest(partial, [], None))["Success"] == "shadow")

    print("\nthe survey decides oversight, the exam does not")
    every = am.build_manifest(high, [], {"signals": {"delegation_style": "human_reviews_every_step"}})
    once = am.build_manifest(high, [], {"signals": {"delegation_style": "human_checkpoint_before_final"}})
    run_hi = am.build_manifest(high, [], {"signals": {"delegation_style": "agent_autonomous",
                                                     "risk_awareness": "high"}})
    run_lo = am.build_manifest(high, [], {"signals": {"delegation_style": "agent_autonomous",
                                                     "risk_awareness": "low"}})
    check("review every step → every agent gated", len(gated(every)) == 6)
    check("one look before final → only outward-facing gated",
          gated(once) == ["Safety", "Switch"], f"got {gated(once)}")
    check("let it run + high risk → outward-facing gated",
          gated(run_hi) == ["Safety", "Switch"])
    check("let it run + low risk → nothing gated by default", gated(run_lo) == [])
    check("same exam score, different survey → different policy",
          gated(every) != gated(run_lo))
    check("no survey profile → survey_led is false",
          am.build_manifest(high, [], None)["survey_led"] is False)
    check("no survey profile → defaults cautious, and says so",
          gated(am.build_manifest(high, [], None)) == ["Safety", "Switch"])

    print("\nthree scored parameters, and only three")
    full = survey(intent_clarity=4, interpretation_gap="partial", effort_source="what",
                  confidence=5, role="operator", transfer="needs a scheduler")
    scored = selfreport.score_selfreport(full, composite=60.0)
    ids = [p["id"] for p in scored["parameters"]]
    check("scores exactly the three parameters", ids == list(selfreport.PARAMETERS), f"got {ids}")
    check("effort_source is context, not a score", "effort_source" in scored["context"])
    check("role is context, not a score", "role" in scored["context"])
    check("free text is carried through", scored["context"]["transfer"]["value"] == "needs a scheduler")

    print("\ncalibration needs both halves")
    check("no measured composite → calibration withheld",
          [p["id"] for p in selfreport.score_selfreport(full, None)["parameters"]]
          == ["intent_clarity", "interpretation_alignment"])
    # Equidistant on purpose: confidence 5 is 1.0 and confidence 1 is 0.0, so a
    # composite of 50 sits exactly 0.5 from each. Being far out in either
    # direction has to cost the same, or the parameter quietly rewards modesty.
    over = selfreport.score_selfreport(survey(confidence=5), composite=50.0)["parameters"][0]
    under = selfreport.score_selfreport(survey(confidence=1), composite=50.0)["parameters"][0]
    check("confidence above measured → positive delta", over["delta"] > 0, f"{over['delta']}")
    check("confidence below measured → negative delta", under["delta"] < 0, f"{under['delta']}")
    check("equal distance either way scores the same",
          over["score"] == under["score"], f"{over['score']} vs {under['score']}")
    exact = selfreport.score_selfreport(survey(confidence=3), composite=50.0)["parameters"][0]
    check("agreement scores 1.0", exact["score"] == 1.0, f"{exact['score']}")

    print("\nabsent is absent, not zero")
    check("no survey at all → answered false, no parameters",
          selfreport.score_selfreport(None, 60.0) == {
              "answered": False, "submitted_at": None, "parameters": [], "context": {},
              "composite": 60.0,
              "note": selfreport.score_selfreport(None, 60.0)["note"]})
    check("unanswered scale is dropped, not read as 1",
          selfreport.score_selfreport(survey(interpretation_gap="matched"), None)
          ["parameters"][0]["id"] == "interpretation_alignment")
    check("out-of-range scale value is dropped",
          selfreport.score_selfreport(survey(intent_clarity=9), None)["parameters"] == [])
    check("unknown categorical is dropped",
          selfreport.score_selfreport(survey(interpretation_gap="terrible"), None)["parameters"] == [])

    print("\nlatest survey wins")
    rows = [survey(intent_clarity=1), {**survey(intent_clarity=5), "ts": 99.0},
            {"kind": "other", "learner": "t@cordiacode.com", "ts": 500.0}]
    check("picks the newest exit survey for that learner",
          selfreport.latest_survey(rows, "t@cordiacode.com")["answers"]["intent_clarity"] == 5)
    check("ignores another learner's survey",
          selfreport.latest_survey(rows, "someone@else.com") is None)

    print("\nnever negative holds on generated copy")
    worst = survey(intent_clarity=1, interpretation_gap="mismatched", effort_source="how",
                   confidence=1, role="curious")
    payload = selfreport.score_selfreport(worst, composite=100.0)
    offenders = surv_types.assert_positive(payload)
    check("worst-case self-report payload is clean", offenders == [], f"found {offenders}")
    man = am.build_manifest(low, ["healthcare"],
                            {"signals": {"delegation_style": "human_reviews_every_step"}})
    check("manifest for an all-low profile is clean",
          surv_types.assert_positive(man) == [], f"found {surv_types.assert_positive(man)}")

    failed = [n for n, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("\nSELF-REPORT + SURVEY-LED ASSIGNMENT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
