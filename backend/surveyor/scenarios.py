#!/usr/bin/env python3
"""Stage 2: situations with a cost attached, and what disagreement means.

WHY THIS EXISTS
---------------
Stage 1 asks people what they prefer. Those answers are predictable from the
question — say you like drawing and the profile calls you visual — so they can
compose a sensible setup but can never surprise anyone.

A scenario answer cannot be guessed from the question, because the question
imposes a trade-off. "Do you want a checkpoint?" is free to say yes to. "Do you
want a checkpoint when it costs you an hour you don't have?" is not. That cost
is the whole mechanism: **every scenario here must make one option genuinely
expensive**, or it degrades into another self-report item and this stage stops
doing anything.

NO RIGHT ANSWERS
----------------
Each option reveals a different way of working; none is better. This is
deliberate and load-bearing. The moment one option is correct, this becomes a
graded instrument that needs rubric validation and two independent raters before
it can be defended — the exact hole the certification is already in. As pure
disposition questions there is nothing to validate.

WHAT WE CLAIM, AND WHAT WE DON'T
--------------------------------
When stated and revealed disagree we report the *fact* — "you said X; when it
cost an hour you chose Y" — which is true regardless of whether the scenario is
well written. The *interpretation* ("aspirational caution") is offered as a
question, never a verdict, because a badly worded scenario would otherwise turn
measurement error into a confident claim about someone's character.

None of this is validated. It cannot be: the data that would validate it is the
data this survey exists to collect.
"""

from __future__ import annotations

# Ordered scales, low -> high, so a disagreement has a direction and a size.
# Only these two dimensions are ordinal; workspace and correction style are
# categorical, and there a mismatch is just a mismatch with no magnitude.
ORDINAL = {
    "delegation_style": ["agent_autonomous",
                         "human_checkpoint_before_final",
                         "human_reviews_every_step"],       # increasing oversight
    "risk_awareness": ["low", "medium", "high"],
}

SCENARIOS = [
    {
        "id": "replies",
        "dimension": "delegation_style",
        "text": ("Here's a situation. Overnight, an agent drafted 40 replies to "
                 "customers. Reading them all properly is about an hour, and you "
                 "don't have an hour today. What do you actually do?"),
        "options": [
            ("human_reviews_every_step", "Read all 40 first"),
            ("human_checkpoint_before_final", "Spot-check a handful, send the rest"),
            ("agent_autonomous", "Send them, deal with any replies"),
        ],
    },
    {
        "id": "unasked",
        "dimension": "correction_style",
        "text": ("You asked for a summary of a supplier contract. It comes back "
                 "accurate and well written — but never mentions the termination "
                 "clause, which you didn't think to ask about. What's your first "
                 "reaction?"),
        "options": [
            ("specific_missing_detail", "It should have flagged what it left out"),
            ("ask_steps", "I'd ask what else it skipped"),
            ("compare_examples", "I'd check it against one I trust"),
            ("rewrite_prompt", "Fair enough — I asked badly"),
        ],
    },
    {
        "id": "errorrate",
        "dimension": "risk_awareness",
        "text": ("A tool turns a two-day job into twenty minutes. But roughly one "
                 "output in twenty has an error you'd only catch by checking it "
                 "yourself. Where do you land?"),
        "options": [
            ("high", "Don't use it until that rate comes down"),
            ("medium", "Use it, but only where a mistake is cheap"),
            ("low", "Use it everywhere — twenty minutes is worth the risk"),
        ],
    },
    {
        "id": "firstglance",
        "dimension": "preferred_workspace",
        "text": ("Last one. You open a tool and it shows four things at once: a "
                 "chat box, a chart of last week's numbers, an open space with a "
                 "few notes scattered on it, and a diagram of how everything "
                 "connects. Which do you look at first?"),
        "options": [
            ("chat_first", "The chat box"),
            ("dashboard", "The chart"),
            ("canvas", "The open space"),
            ("graph_and_chat", "The diagram"),
        ],
    },
]

BY_ID = {s["id"]: s for s in SCENARIOS}
IDS = [s["id"] for s in SCENARIOS]


def choices_for(scenario_id):
    s = BY_ID.get(scenario_id)
    return [{"value": v, "label": l} for v, l in s["options"]] if s else []


def valid_choice(scenario_id, value) -> bool:
    s = BY_ID.get(scenario_id)
    return bool(s) and any(v == value for v, _ in s["options"])


def next_scenario(answered):
    for sid in IDS:
        if sid not in (answered or {}):
            return BY_ID[sid]
    return None


def next_scenario_excluding(answers, attempted=()):
    """Next unanswered scenario not already presented in this conversation."""
    answers = answers if isinstance(answers, dict) else {}
    blocked = {item for item in attempted or () if item in IDS}
    for scenario in SCENARIOS:
        if scenario["id"] not in blocked and not answers.get(scenario["id"]):
            return scenario
    return None


# ---------------------------------------------------------------- tensions

# Keyed by (dimension, direction). direction is 'less' when the person revealed
# LESS of the trait than they claimed, 'more' when they revealed more.
#
# `fact` is filled in from their actual answers and is true either way.
# `reading` is a hypothesis about what it might mean, and is phrased as one.
MEANING = {
    ("delegation_style", "less"): {
        "name": "Oversight you believe in more than you practise",
        "reading": ("It may be that the check matters to you but doesn't survive a "
                    "busy day — which is an argument for making it automatic rather "
                    "than something you have to choose."),
        "do": ("Build the checkpoint into the workflow so it costs you nothing. "
               "Don't design anything that depends on you deciding to review."),
    },
    ("delegation_style", "more"): {
        "name": "More careful in practice than in description",
        "reading": ("You may be more comfortable with autonomy than you'd say, as "
                    "long as you can satisfy the urge to check quickly."),
        "do": ("Give the agent more room, but keep a visible trail you can scan in "
               "seconds rather than re-reading the work."),
    },
    ("risk_awareness", "less"): {
        "name": "A higher tolerance for risk than stated",
        "reading": ("Your line may be less about risk in the abstract and more "
                    "about where a mistake would actually be seen."),
        "do": ("Set the hard stop at anything visible to someone else, and let it "
               "move freely everywhere behind that line."),
    },
    ("risk_awareness", "more"): {
        "name": "More cautious in the moment than in principle",
        "reading": ("Concrete stakes seem to move you more than the general idea of "
                    "risk does."),
        "do": ("Decide the stopping rules once, in advance, rather than judging "
               "each case as it arrives."),
    },
}

CATEGORICAL = {
    "preferred_workspace": {
        "name": "Your attention went somewhere other than you'd expect",
        "reading": ("What someone reaches for first isn't always what they'd design "
                    "for themselves."),
        "do": "Start with what you looked at first, and keep the rest one click away.",
    },
    "correction_style": {
        "name": "You spot problems differently than you'd describe",
        "reading": "How you describe reviewing work and how you actually review it can differ.",
        "do": "Ask the agent to state what it left out, not just what it did.",
    },
}


def revealed_signals(profile) -> dict:
    """Stage-2 choices as {dimension: value}.

    This is where "the scenario wins" is actually enforced. Without it the
    recommendation happily prints a tension explaining that someone's stated
    oversight doesn't survive a busy day, and then two sections later tells them
    to review every step — which is the stated answer the tension just
    contradicted.
    """
    out = {}
    for sid, value in (profile.get("scenarios") or {}).items():
        s = BY_ID.get(sid)
        if s and s.get("dimension") and value:
            out[s["dimension"]] = value
    return out


def effective(profile) -> dict:
    """Stated signals with revealed choices layered on top."""
    merged = dict(profile.get("signals") or {})
    merged.update(revealed_signals(profile))
    return merged


def _rank(dimension, value):
    scale = ORDINAL.get(dimension)
    return scale.index(value) if scale and value in scale else None


def find_tensions(signals, answers) -> list:
    """Compare stage-1 statements against stage-2 choices.

    Returns one entry per cross-checked dimension where they differ. Agreement
    is reported too (as agreed=True) because a person whose answers line up is
    telling us their self-report is worth trusting.
    """
    out = []
    for sid, revealed in (answers or {}).items():
        s = BY_ID.get(sid)
        if not s:
            continue
        dim = s.get("dimension")
        stated = (signals or {}).get(dim)
        if not dim or not stated:
            continue

        if stated == revealed:
            out.append({"scenario": sid, "dimension": dim, "agreed": True,
                        "stated": stated, "revealed": revealed, "gap": 0})
            continue

        a, b = _rank(dim, stated), _rank(dim, revealed)
        gap = (b - a) if (a is not None and b is not None) else None
        direction = None if gap is None else ("more" if gap > 0 else "less")
        meaning = MEANING.get((dim, direction)) if direction else CATEGORICAL.get(dim)

        out.append({
            "scenario": sid, "dimension": dim, "agreed": False,
            "stated": stated, "revealed": revealed,
            "gap": gap, "direction": direction,
            "name": (meaning or {}).get("name"),
            "reading": (meaning or {}).get("reading"),
            "do": (meaning or {}).get("do"),
        })
    return out


def reliability(tensions) -> dict:
    """How closely this person's self-report matched what they chose.

    RECORDED, NOT ACTED ON. The idea is that agreement on cross-checked
    dimensions is evidence about how literally to take the nine stage-1 answers
    that are never cross-checked. That's a hypothesis. Turning it into a
    multiplier would mean inventing the constant we deliberately avoided
    inventing, so this is stored for later analysis and changes nothing today.
    """
    checked = [t for t in tensions if t.get("dimension")]
    if not checked:
        return {"checked": 0, "agreed": 0, "ordinal_gap_mean": None, "mismatches": 0}
    gaps = [abs(t["gap"]) for t in checked if isinstance(t.get("gap"), int)]
    return {
        "checked": len(checked),
        "agreed": sum(1 for t in checked if t.get("agreed")),
        "mismatches": sum(1 for t in checked if not t.get("agreed")),
        "ordinal_gap_mean": round(sum(gaps) / len(gaps), 3) if gaps else None,
        "note": "recorded for analysis; does not affect any recommendation",
    }
