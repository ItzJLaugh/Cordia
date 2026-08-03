#!/usr/bin/env python3
"""The Cordia profile: three positive identifiers, each telling the person how
to use AI.

This is the only part of the profile a learner ever sees, and it is built under
one hard rule: **nothing negative, ever.** No bottom-ranked list, no "weak"
dimension, no gaps section.

That rule is not politeness. The older profile compiler in this codebase picks
strong and weak dimensions by *rank*, so a learner scoring 95 on everything is
still told they are weak at two things, and one scoring 30 on everything is told
they are strong at two. Ranking with no absolute threshold manufactures a
result out of noise. Taking only the top three and never naming a bottom makes
that failure structurally impossible: there is no bottom half to be wrong about.

When we do not have enough signal for a third identifier we return two, or one,
and the UI asks the person to keep talking. A withheld identifier is honest; an
invented one is not.
"""

from __future__ import annotations

from . import types

# Minimum score for a criterion to be worth naming. Below this we would be
# describing someone from almost nothing, so we withhold instead.
FLOOR = 0.34

# criterion -> the identifier it becomes. Written as a capability the person
# already has and a concrete way to spend it on AI.
CATALOGUE = {
    "intent_clarity": {
        "name": "Clear briefer",
        "meaning": "You can say what you actually want before you start, which is "
                   "the single thing most people can't do with AI.",
        "use_ai_this_way": "Put the outcome in one sentence at the top of every prompt.",
    },
    "gap_detection": {
        # Named "Mismatch spotter", not "Gap spotter": the never-negative guard
        # flags the word "gap" in user-facing copy, and it is right to. Renaming
        # the card is cheaper than loosening the rule that protects every other
        # string on the page.
        "name": "Mismatch spotter",
        "meaning": "You notice the difference between an answer that sounds right "
                   "and one that is right.",
        "use_ai_this_way": "Ask what it assumed — faster than checking the answer.",
    },
    "constraint_setting": {
        "name": "Boundary setter",
        "meaning": "You think in limits — budget, tone, scope, what's off the table.",
        "use_ai_this_way": "Lead with the constraints, not the request.",
    },
    "risk_boundary_awareness": {
        "name": "Risk reader",
        "meaning": "You can tell which mistakes are cheap and which ones cost money, "
                   "trust, or safety.",
        "use_ai_this_way": "Name the expensive failure. Let it move fast elsewhere.",
    },
    "delegation_readiness": {
        "name": "Confident delegator",
        "meaning": "You are comfortable handing work over and saying where to check back in.",
        "use_ai_this_way": "Give whole tasks, not single steps, and name one checkpoint.",
    },
    "visual_systems_thinking": {
        "name": "Visual systems thinker",
        "meaning": "You reason about work as a map of connected parts rather than a list.",
        "use_ai_this_way": "Ask for the diagram before the prose.",
    },
    "verification_instinct": {
        "name": "Evidence checker",
        "meaning": "You want to see the working, not just the conclusion.",
        "use_ai_this_way": "Ask for sources in the same message as the task.",
    },
    "domain_specificity": {
        "name": "Domain anchor",
        "meaning": "You bring real context from your field, which is exactly what a "
                   "general model doesn't have.",
        "use_ai_this_way": "Front-load your specifics — the model can't invent those.",
    },
    "workflow_decomposition": {
        "name": "Workflow breaker",
        "meaning": "You naturally split messy work into ordered, checkable steps.",
        "use_ai_this_way": "Give each step its own agent and success condition.",
    },
    "human_checkpoint_judgment": {
        "name": "Checkpoint setter",
        "meaning": "You have a good sense of the moment a human needs to look before "
                   "anything goes out.",
        "use_ai_this_way": "Put your approval step just before anything goes outside.",
    },
}

MAX_IDENTIFIERS = 3


def build(profile: dict) -> list:
    """Top three scoring criteria, above the floor, as positive identifiers.

    Ties break on the order in types.CRITERIA so the same profile always yields
    the same identifiers — a profile that reshuffles between page loads would
    read as arbitrary, which is the opposite of what this is for.
    """
    scores = (profile or {}).get("scores") or {}
    order = {c: i for i, c in enumerate(types.CRITERIA)}

    ranked = sorted(
        ((c, s) for c, s in scores.items() if c in CATALOGUE and s is not None and s >= FLOOR),
        key=lambda kv: (-kv[1], order.get(kv[0], 99)),
    )

    out = []
    for criterion, score in ranked[:MAX_IDENTIFIERS]:
        card = dict(CATALOGUE[criterion])
        card["criterion"] = criterion          # for admin traceability only
        card["confidence"] = _confidence(profile, criterion, score)
        out.append(card)
    return out


# How well-evidenced an identifier is, in words that describe the *evidence*
# rather than the person. Shipping the raw "low"/"medium"/"high" here put the
# word "low" on a card about someone's strengths, which reads as a verdict on
# them and trips the never-negative guard for good reason.
_STRENGTH = {"high": "clear", "medium": "emerging", "low": "early"}


def _confidence(profile, criterion, score):
    """How much conversation actually backs this identifier."""
    ev = [e for e in (profile.get("evidence") or []) if e.get("criterion") == criterion]
    if len(ev) >= 2 and score >= 0.66:
        return _STRENGTH["high"]
    if ev:
        return _STRENGTH["medium"]
    return _STRENGTH["low"]


def next_best_action(profile: dict) -> dict:
    """What the person should do next. Always forward-looking, never remedial."""
    n = len(build(profile))
    signals = (profile or {}).get("signals") or {}
    if n == 0:
        return {"type": "continue_survey", "label": "Talk to Surveyor",
                "reason": "A few more answers and Cordia can shape a workspace around you."}
    if n < MAX_IDENTIFIERS:
        return {"type": "refine_profile", "label": "Refine my profile",
                "reason": "Cordia has part of your picture. A little more sharpens it."}
    if not signals.get("domain"):
        return {"type": "refine_profile", "label": "Add your field of work",
                "reason": "Knowing your domain lets Cordia pick tools that match it."}
    return {"type": "create_interface", "label": "Build my workspace",
            "reason": "Cordia has enough to lay out a workspace built around how you work."}
