#!/usr/bin/env python3
"""Score the ten hidden criteria from accumulated signals and evidence.

Two things this deliberately is not:

1. **Not a grade.** These numbers are internal. They pick which three positive
   identifiers a person sees and how their workspace is laid out. They are never
   shown as a result, never compared between people, and never touch the
   certification score.

2. **Not keyword matching.** Scoring reads the *validated signals* the extractor
   produced from what someone meant, plus how much evidence backs each one.
   A raw word in a message cannot move a score on its own. That rule exists
   because this codebase already shipped a keyword-substring scorer once, and it
   scored a real user 0/3 for quoting the question back.

Unobserved criteria are absent, not zero. "Not asked yet" and "asked and low"
are different facts, and a criterion we never probed must never be able to look
like a measured weakness.
"""

from __future__ import annotations

from . import types

_LEVEL = {"low": 0.25, "medium": 0.6, "high": 0.9}

# criterion -> signals that support it, and how much each contributes.
# Several criteria are supported by more than one signal so that no single
# answer can dominate a score on its own.
_FROM_SIGNALS = {
    "visual_systems_thinking": {
        "graph_preference": 0.5, "drawing_preference": 0.3, "visual_preference": 0.2,
    },
    "risk_boundary_awareness": {"risk_awareness": 1.0},
    "domain_specificity": {"domain": 0.7, "work_type": 0.3},
    "intent_clarity": {"primary_goal": 0.6, "domain": 0.4},
}

# categorical signals that map to a criterion value directly
_FROM_CATEGORY = {
    "delegation_readiness": ("delegation_style", {
        "agent_autonomous": 0.9,
        "human_checkpoint_before_final": 0.65,
        "human_reviews_every_step": 0.35,
    }),
    "human_checkpoint_judgment": ("delegation_style", {
        "human_checkpoint_before_final": 0.9,
        "human_reviews_every_step": 0.6,
        "agent_autonomous": 0.4,
    }),
    "verification_instinct": ("verification_preference", {
        "evidence_first": 0.9, "example_first": 0.6, "speed_first": 0.3,
    }),
    "gap_detection": ("correction_style", {
        "specific_missing_detail": 0.9,
        "compare_examples": 0.7,
        "ask_steps": 0.6,
        "rewrite_prompt": 0.4,
    }),
    "workflow_decomposition": ("correction_style", {
        "ask_steps": 0.85, "specific_missing_detail": 0.6,
        "compare_examples": 0.5, "rewrite_prompt": 0.4,
    }),
    "constraint_setting": ("interface_density", {
        "detailed": 0.8, "balanced": 0.6, "minimal": 0.4,
    }),
}

# Role tendency nudges a few criteria, but only as a small adjustment. It is a
# self-description, and self-description is a weak prior — it may tilt a score,
# never set one.
_ROLE_NUDGE = {
    "analyzer": {"verification_instinct": 0.08, "gap_detection": 0.05},
    "prototyper": {"workflow_decomposition": 0.08, "delegation_readiness": 0.05},
    "manager": {"human_checkpoint_judgment": 0.08, "delegation_readiness": 0.05},
    "human_facing": {"intent_clarity": 0.05, "risk_boundary_awareness": 0.05},
    "technical_specialist": {"domain_specificity": 0.08, "constraint_setting": 0.05},
}

_EVIDENCE_WEIGHT = {"low": 0.02, "medium": 0.05, "high": 0.08}
_MAX_EVIDENCE_LIFT = 0.15


def _signal_value(signals, name):
    """A signal's numeric strength, or None if we don't have it."""
    v = signals.get(name)
    if v is None:
        return None
    if isinstance(v, str):
        return _LEVEL.get(v.lower(), 0.6 if v.strip() else None)
    if isinstance(v, list):
        return 0.75 if v else None
    return None


def score(profile: dict) -> dict:
    """Return {criterion: 0..1} for observed criteria only."""
    signals = (profile or {}).get("signals") or {}
    evidence = (profile or {}).get("evidence") or []
    out = {}

    for criterion, contributors in _FROM_SIGNALS.items():
        total = weight_seen = 0.0
        for sig, w in contributors.items():
            v = _signal_value(signals, sig)
            if v is not None:
                total += v * w
                weight_seen += w
        if weight_seen:
            out[criterion] = total / weight_seen      # normalise by what we saw

    for criterion, (sig, table) in _FROM_CATEGORY.items():
        v = signals.get(sig)
        if isinstance(v, str) and v in table:
            out[criterion] = table[v]

    role = signals.get("role_tendency")
    for criterion, delta in _ROLE_NUDGE.get(role, {}).items():
        if criterion in out:
            out[criterion] = out[criterion] + delta

    # Corroboration lifts a score slightly — someone who returned to the same
    # theme unprompted is better evidenced than someone who mentioned it once.
    lift = {}
    for e in evidence:
        c = e.get("criterion")
        if c in out:
            lift[c] = min(_MAX_EVIDENCE_LIFT,
                          lift.get(c, 0.0) + _EVIDENCE_WEIGHT.get(e.get("confidence"), 0.02))
    for c, l in lift.items():
        out[c] += l

    # Evidence alone can open a criterion the signals never covered, but only
    # to a modest value — it is one remark, not a demonstrated capability.
    for e in evidence:
        c = e.get("criterion")
        if c in types.CRITERIA and c not in out:
            out[c] = max(out.get(c, 0.0),
                         0.4 if e.get("confidence") == "high" else 0.35)

    return {c: round(max(0.0, min(1.0, v)), 3) for c, v in out.items()}


def confidence(profile: dict) -> float:
    """How much of the picture we actually have. Drives the progress bar and
    whether an identifier is shown or withheld."""
    signals = (profile or {}).get("signals") or {}
    evidence = (profile or {}).get("evidence") or []
    breadth = min(1.0, len([s for s in types.SIGNAL_PRIORITY if signals.get(s)])
                  / float(types.ENOUGH_SIGNALS))
    depth = min(1.0, len(evidence) / 10.0)
    return round(0.7 * breadth + 0.3 * depth, 3)
