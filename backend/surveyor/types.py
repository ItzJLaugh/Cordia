#!/usr/bin/env python3
"""Surveyor profile shape, vocabularies, and validation.

Two halves, deliberately separated:

  signals + scores   internal. Ordinal and numeric, low values included.
                     Admin/debug only. Feeds the next scoring layer.

  identifiers        user-facing. Exactly three, always positive, each one
                     carrying a concrete recommendation for how to use AI.

The separation is the point. Intent cannot be measured, but it can be surveyed,
and what a person gets back should tell them how to work — not rank them. No
user-facing payload ever contains a deficit, a "weak" label, or a gap list.

Everything here is an allow-list. The extractor runs an LLM, and an LLM will
eventually return a key we never designed for, a score of 4.7, or the string
"high" where an object was expected. Nothing downstream should have to defend
itself, so validation happens once, here, and drops silently rather than
raising — a malformed extraction must never cost the user their profile.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------- criteria

# The ten hidden criteria. Scored 0..1 with evidence. Never shown to the learner.
CRITERIA = (
    "intent_clarity",
    "gap_detection",
    "constraint_setting",
    "risk_boundary_awareness",
    "delegation_readiness",
    "visual_systems_thinking",
    "verification_instinct",
    "domain_specificity",
    "workflow_decomposition",
    "human_checkpoint_judgment",
)

CONFIDENCE = ("low", "medium", "high")
SOURCES = ("surveyor_conversation", "behavior", "manual")

# ---------------------------------------------------------------- signals

LEVELS = ("low", "medium", "high", "unknown")

ROLE_TENDENCY = (
    "prototyper", "analyzer", "manager",
    "human_facing", "technical_specialist", "mixed", "unknown",
)

WORKSPACE = ("chat_first", "dashboard", "canvas", "graph_and_chat", "balanced", "unknown")
DENSITY = ("minimal", "balanced", "detailed", "unknown")
CORRECTION_STYLE = ("specific_missing_detail", "rewrite_prompt", "compare_examples",
                    "ask_steps", "unknown")
DELEGATION_STYLE = ("agent_autonomous", "human_checkpoint_before_final",
                    "human_reviews_every_step", "unknown")
VERIFICATION_PREF = ("evidence_first", "speed_first", "example_first", "unknown")

# signal name -> allowed values. Free-text signals map to None.
SIGNAL_SCHEMA = {
    "domain": None,
    "primary_goal": None,
    "work_type": None,                      # list of free-text strings
    "role_tendency": ROLE_TENDENCY,
    "visual_preference": LEVELS,
    "graph_preference": LEVELS,
    "drawing_preference": LEVELS,
    "verbal_preference": LEVELS,
    "preferred_workspace": WORKSPACE,
    "interface_density": DENSITY,
    "risk_awareness": LEVELS,
    "correction_style": CORRECTION_STYLE,
    "delegation_style": DELEGATION_STYLE,
    "verification_preference": VERIFICATION_PREF,
}

# Signals worth asking about, best-value first. question_strategy walks this.
SIGNAL_PRIORITY = (
    "domain",
    "role_tendency",
    "primary_goal",
    "graph_preference",
    "drawing_preference",
    "risk_awareness",
    "delegation_style",
    "preferred_workspace",
    "verbal_preference",
    "visual_preference",
    "correction_style",
    "verification_preference",
    "interface_density",
)

# Enough signal to stop asking and offer a setup recommendation.
#
# 9 of the 13 priority signals — about 10-12 questions once the opener and the
# close are counted. Below roughly 8 the recommendation has little to say about
# surface, role and risk posture together; much above 10 and the survey starts
# asking more than most people will finish. This is a judgement call, and real
# completion data should override it.
ENOUGH_SIGNALS = 9

_MAX_TEXT = 400
_MAX_LIST = 8


def empty_profile() -> dict:
    return {
        "signals": {},
        "scores": {},
        "evidence": [],
        "identifiers": [],
        "adaptation": {},
        "scenarios": {},
        "freeform": {},
        "intent_misses": [],
        "tensions": [],
        "reliability": {},
        "confidence": 0.0,
        "questions_answered": 0,
        "simple_mode_forced": False,
    }


# ---------------------------------------------------------------- validation

def _clean_text(v):
    if not isinstance(v, str):
        return None
    v = v.strip()
    return v[:_MAX_TEXT] if v else None


def validate_signals(raw) -> dict:
    """Keep only known signals with legal values. Drop everything else.

    Silent by design: an LLM that invents `enthusiasm: "very high"` should cost
    us that one key, not the request.
    """
    if not isinstance(raw, dict):
        return {}
    out = {}
    for name, allowed in SIGNAL_SCHEMA.items():
        if name not in raw:
            continue
        v = raw[name]
        if name == "work_type":
            if isinstance(v, str):
                v = [v]
            if isinstance(v, list):
                items = [t for t in (_clean_text(x) for x in v) if t][:_MAX_LIST]
                if items:
                    out[name] = items
            continue
        if allowed is None:
            t = _clean_text(v)
            if t:
                out[name] = t
            continue
        if isinstance(v, str) and v.strip().lower() in allowed:
            val = v.strip().lower()
            if val != "unknown":            # "unknown" is absence; don't store it
                out[name] = val
    return out


def _clamp01(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:                              # NaN
        return None
    return max(0.0, min(1.0, f))


def validate_scores(raw) -> dict:
    """Keep known criteria only, clamped to 0..1. Non-numeric is dropped, not zeroed.

    Dropping rather than zeroing matters: "not yet observed" and "observed as
    zero" are different facts, and conflating them would let a criterion we
    never asked about look like a measured weakness. Same discipline the 6S
    store applies to unmeasured cells.
    """
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k in CRITERIA:
        if k in raw:
            f = _clamp01(raw[k])
            if f is not None:
                out[k] = f
    return out


def validate_evidence(raw) -> list:
    if not isinstance(raw, list):
        return []
    out = []
    for e in raw[:40]:
        if not isinstance(e, dict):
            continue
        crit = e.get("criterion")
        summary = _clean_text(e.get("summary"))
        if crit not in CRITERIA or not summary:
            continue
        conf = e.get("confidence")
        src = e.get("source")
        out.append({
            "criterion": crit,
            "summary": summary,
            "confidence": conf if conf in CONFIDENCE else "low",
            "source": src if src in SOURCES else "surveyor_conversation",
        })
    return out


def merge_profile(current: dict, extracted: dict) -> dict:
    """Fold a validated extraction into the stored profile.

    Later observations win on signals (people clarify themselves mid-conversation),
    evidence accumulates, and scores are recomputed by the scorer rather than
    trusted from the model.
    """
    out = dict(current or empty_profile())
    signals = dict(out.get("signals") or {})
    signals.update(validate_signals(extracted.get("signals")))
    out["signals"] = signals
    out["evidence"] = (list(out.get("evidence") or []) +
                       validate_evidence(extracted.get("evidence")))[-60:]
    return out


def profile_completeness(profile: dict) -> float:
    """0..1 across all three survey stages.

    Weighted by how much each stage contributes rather than by question count:
    stage 1 composes the setup, stage 2 is the only stage that can contradict
    stage 1, and stage 3 is the only stage that describes the actual work. A
    person who stops after stage 1 should see real progress, not 90%.
    """
    p = profile or {}
    signals = p.get("signals") or {}
    have = sum(1 for s in SIGNAL_PRIORITY if signals.get(s))
    prefs = min(1.0, have / float(ENOUGH_SIGNALS))

    from . import freeform, scenarios
    scn = len(p.get("scenarios") or {}) / float(len(scenarios.IDS))
    free = freeform.answered_count(p.get("freeform") or {}) / float(len(freeform.KEYS))
    return round(min(1.0, 0.45 * prefs + 0.30 * min(1.0, scn) + 0.25 * min(1.0, free)), 3)


# ---------------------------------------------------------------- guard rail

# Words that must never reach a user-facing payload. Asserted in tests and
# enforced at the response boundary, because the never-negative rule is a
# product promise and not merely a style preference.
# "behind" is deliberately absent: "the evidence behind it" is innocent copy,
# and the deficit sense ("falling behind") is already covered by the rest.
NEGATIVE_WORDS = ("weak", "weaker", "weakness", "weaknesses", "low", "lower",
                  "poor", "poorly", "deficit", "gap", "gaps", "lacking", "lack",
                  "lacks", "deficiency", "below", "struggles", "struggle",
                  "worse", "worst", "insufficient", "missing")

# Matched on whole words only. A naive substring check flags "workflow" for
# containing "low" and "gap analysis" inside an unrelated noun — which is how
# the first version of this guard produced 1615 false positives across a 3000
# profile sweep while missing nothing real.
_NEGATIVE_RE = re.compile(r"\b(?:%s)\b" % "|".join(sorted(NEGATIVE_WORDS, key=len, reverse=True)))


def assert_positive(payload) -> list:
    """Return the offending words found in a user-facing payload. Empty is good."""
    import json as _json
    blob = _json.dumps(payload, ensure_ascii=False).lower()
    return sorted(set(_NEGATIVE_RE.findall(blob)))
