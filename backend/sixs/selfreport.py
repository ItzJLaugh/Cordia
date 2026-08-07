#!/usr/bin/env python3
"""The three self-report parameters that score alongside the 6S matrix.

WHY THIS EXISTS
---------------
The 6S matrix measures what a learner *wrote*. It cannot see three things that
only the learner knows, and that no amount of grading their text will recover:

    1. how clear they were on what they wanted, before they started writing
    2. whether the exercises read their answers the way they meant them
    3. whether their confidence matched what they could actually do

Those are the exit survey's job. This module turns them into three scored
parameters on the same 0..1 scale as a 6S dimension composite, so an assessment
can carry nine measures rather than six.

WHAT IS AND IS NOT A SCORE HERE
-------------------------------
Three of the six exit-survey answers admit a quality score. The other three do
not, and are deliberately kept as *context* rather than dressed up as measures:

    scored      intent_clarity, interpretation_alignment, calibration
    context     effort_source, role, transfer

`effort_source` says whether the work went into deciding *what* to ask for or
*how* to phrase it. Neither is better, so scoring it would invent a direction
that the question does not have. `role` is a self-description, and `transfer` is
free text about the product. Both belong in the assessment; neither is a
measure of the person.

CALIBRATION IS THE ONLY ONE THAT NEEDS THE 6S SCORE
---------------------------------------------------
`intent_clarity` and `interpretation_alignment` stand on their own. Calibration
is the signed distance between how confident someone said they were and how they
actually scored, so it exists only where a 6S composite exists. It is also the
one parameter here that cannot be talked up: claiming high confidence moves it
away from zero unless the work backs the claim.

NEVER NEGATIVE
--------------
Everything in the `public` payload is written to survive
`surveyor.types.assert_positive()`. That rule is a product promise, and it binds
this module for the same reason it binds the Surveyor profile: a person reading
their own assessment must not be handed a deficit. Where a parameter is low we
say less, or we say what to do — we never name a shortfall.

Unanswered is absent, never zero. Same discipline as the 6S matrix and the
Surveyor scorer: "not asked" and "answered at the bottom of the scale" are
different facts, and collapsing them would let a question nobody answered look
like a measured result.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "PARAMETERS",
    "SURVEY_KIND",
    "score_selfreport",
    "latest_survey",
]

SURVEY_KIND = "aie1-exit-survey"

# The three scored parameters, in the order an assessment should present them.
PARAMETERS = ("intent_clarity", "interpretation_alignment", "calibration")

# Exit-survey answer keys this module reads. Kept explicit so a change to the
# survey form fails loudly here rather than silently scoring nothing.
_SCALE_MAX = 5

_ALIGNMENT_LEVELS = {
    "matched": 1.0,
    "partial": 0.5,
    "mismatched": 0.0,
}

# Context values we pass through untouched. Listed so an unexpected value from
# an older survey version is dropped rather than rendered into an assessment.
_EFFORT_SOURCE = {
    "what": "Deciding what to ask for",
    "how": "Working out how to say it",
    "equal": "Evenly split",
}

_ROLE = {
    "operator": "Directs AI agents already",
    "managed": "AI agents are used on their work",
    "evaluating": "Evaluating whether to adopt",
    "curious": "Learning for now",
}


def _scale01(v: Any) -> float | None:
    """A 1..5 survey scale as 0..1, or None when unanswered.

    1 maps to 0.0 and 5 to 1.0. Out-of-range values are dropped rather than
    clamped: a 7 on a five-point scale means the form and this module disagree,
    and quietly reading it as 1.0 would hide that.
    """
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    if not 1 <= n <= _SCALE_MAX:
        return None
    return round((n - 1) / (_SCALE_MAX - 1), 3)


def _intent_clarity(answers: dict) -> dict | None:
    v = _scale01(answers.get("intent_clarity"))
    if v is None:
        return None
    return {
        "id": "intent_clarity",
        "label": "Intent clarity",
        "score": v,
        "source": "self-report",
        "means": "How settled you were on the outcome before you started writing.",
    }


def _interpretation_alignment(answers: dict) -> dict | None:
    raw = answers.get("interpretation_gap")
    if not isinstance(raw, str) or raw not in _ALIGNMENT_LEVELS:
        return None
    return {
        "id": "interpretation_alignment",
        "label": "Interpretation alignment",
        "score": _ALIGNMENT_LEVELS[raw],
        "source": "self-report",
        "means": "How closely the exercises read your answers the way you meant them.",
    }


def _calibration(answers: dict, composite: float | None) -> dict | None:
    """Self-reported confidence against measured performance.

    `composite` is the 6S final composite on its native 0-100 scale, or None
    when nothing has been measured yet. Without it there is no calibration to
    compute — confidence on its own is a feeling, not a parameter — so this
    returns None rather than reporting confidence as though it were a score.

    `delta` is signed and deliberately kept in the payload: positive means
    confidence ran ahead of the measured work, negative means the work came out
    stronger than the person expected. `score` is 1.0 at perfect agreement and
    falls off with distance in either direction, so being far out in *either*
    direction costs the same.
    """
    confidence = _scale01(answers.get("confidence"))
    if confidence is None or composite is None:
        return None
    measured = max(0.0, min(1.0, float(composite) / 100.0))
    delta = round(confidence - measured, 3)
    return {
        "id": "calibration",
        "label": "Calibration",
        "score": round(1.0 - abs(delta), 3),
        "delta": delta,
        "confidence": confidence,
        "measured": round(measured, 3),
        "source": "self-report vs measured",
        "means": "How closely your read on your own answers matched how they scored.",
        "reading": _calibration_reading(delta),
    }


# Phrased so none of these can land as a verdict on the person. The middle case
# is the good one; both edges are stated as something to do next, not a fault.
# "underconfident" and "overconfident" are deliberately absent — they are labels
# about a person, and the never-negative rule does not make an exception for
# labels that happen to be accurate.
def _calibration_reading(delta: float) -> str:
    if abs(delta) <= 0.15:
        return "Your read on your own work matched how it scored. Trust that instinct."
    if delta > 0:
        return ("You backed your answers harder than the scoring did. Ask an agent to "
                "state what it assumed before you accept a result that feels right.")
    return ("Your answers scored above your own read of them. Give yourself the first "
            "call more often, and use a checkpoint to confirm rather than to decide.")


def _context(answers: dict) -> dict:
    """The three answers that are not measures. Passed through, never scored.

    `transfer` is the learner's own free text and is returned verbatim. It is
    the one string in this payload that `assert_positive()` may legitimately
    flag — someone describing what their setup is missing will write "missing" —
    so run that guard over the generated copy, not over a person's own words.
    Same treatment `recommendation.py` gives quoted freeform.
    """
    out: dict[str, Any] = {}
    effort = answers.get("effort_source")
    if isinstance(effort, str) and effort in _EFFORT_SOURCE:
        out["effort_source"] = {"value": effort, "label": _EFFORT_SOURCE[effort],
                                "means": "Where the work went. Neither answer is better."}
    role = answers.get("role")
    if isinstance(role, str) and role in _ROLE:
        out["role"] = {"value": role, "label": _ROLE[role],
                       "means": "Shapes which setup template fits your situation."}
    transfer = answers.get("transfer")
    if isinstance(transfer, str) and transfer.strip():
        out["transfer"] = {"value": transfer.strip()[:2000],
                           "means": "Your words about what the compiled system is missing."}
    return out


def latest_survey(rows, learner: str) -> dict | None:
    """The most recent exit-survey record for one learner, or None.

    `rows` is the raw corpus, which holds exam responses and survey records
    together. Filtering on both `kind` and `learner` here means no caller has to
    remember that the two live in the same file.
    """
    best = None
    best_ts = -1.0
    for r in rows or []:
        if r.get("kind") != SURVEY_KIND or r.get("learner") != learner:
            continue
        ts = float(r.get("ts") or 0)
        if ts >= best_ts:
            best_ts = ts
            best = r
    return best


def score_selfreport(survey_rec: dict | None, composite: float | None = None) -> dict:
    """Turn one exit-survey record into three scored parameters plus context.

    Returns a payload that is safe to hand straight to a browser:

        answered      bool — whether a survey record was found at all
        parameters    [{id, label, score, means, ...}] for those we could score
        context       effort_source / role / transfer, unscored
        composite     the 6S composite calibration was measured against, if any

    A missing survey is not an error. It is the ordinary state for anyone who
    has not finished the exam yet, and the assessment renders without these
    three parameters rather than blocking on them.
    """
    answers = (survey_rec or {}).get("answers") or {}
    if not isinstance(answers, dict):
        answers = {}

    scored = [p for p in (_intent_clarity(answers),
                          _interpretation_alignment(answers),
                          _calibration(answers, composite)) if p]

    return {
        "answered": bool(survey_rec),
        "submitted_at": (survey_rec or {}).get("ts"),
        "parameters": scored,
        "context": _context(answers),
        "composite": composite,
        "note": ("Three parameters only you could report, scored alongside the six "
                 "measured from your written answers."),
    }
