#!/usr/bin/env python3
"""Micro-classifier judging spine for CordiaAIE — standard library only.

Sits between the anchor scorer (scorer.py / aie_map.py, which blends
structural regex against semantic distance into a single number) and a
future reasoning-model catch-net that has not been built yet. This layer
does neither of those jobs. It decomposes one answer into a handful of
independent STRUCTURAL FEATURES — did the learner state a trigger, a
negation, a named actor, a verification step — and reports which fired,
with the literal evidence fragment for each. It never touches a score.

Why a separate layer instead of folding this into aie_map.STRUCTURAL_CHECKS:
those checks are a flat bag of regexes averaged into one percentage, so a
learner who nails three concepts and misses one is indistinguishable from a
learner who half-matches all four. The judge keeps every feature named and
inspectable, and turns the margin into a routing decision — deliver the
verdict, or forward to a reasoning model for the cases a keyword classifier
cannot resolve on its own. That forwarding path is a stub today
(forward_to_reasoning_model just records the need) because the catch-net
does not exist yet; wiring the escalation path now means it is exercised
end-to-end before there is anything on the other end of it.

FRAME FORMAT (judge_answer return value, stable keys):
    {
      "block":    str,
      "features": [{"name": str, "result": "hit"|"miss"|"na", "evidence": str}, ...],
      "hits":     int,
      "total":    int,
      "margin":   float,   # hits / total
      "verdict":  "strong" | "partial" | "weak",
    }
"""

from __future__ import annotations

import re
from typing import Callable, NamedTuple

__all__ = [
    "FeatureResult",
    "FEATURES",
    "BLOCK_FEATURES",
    "judge_answer",
    "forward_to_reasoning_model",
]


class FeatureResult(NamedTuple):
    name: str
    result: str      # "hit" | "miss" | "na"
    evidence: str     # matched fragment, or "" when miss/na


# ---------------------------------------------------------------------------
# FEATURE LIBRARY
#
# Every feature is a function text -> FeatureResult. Patterns are flat
# word-alternations (`\b(a|b|c)\b`) with no nested quantifiers or repeated
# groups, so there is nothing for catastrophic backtracking to catch on —
# same discipline as aie_map.py's concept-class regexes. A blank answer
# short-circuits to "na" for every feature: there is no structure to judge,
# so it would be dishonest to call that a "miss" the same way a wrong answer
# is a miss.
# ---------------------------------------------------------------------------

def _make_regex_feature(name: str, pattern: "re.Pattern[str]") -> Callable[[str], FeatureResult]:
    def feature(text: str) -> FeatureResult:
        if not text or not text.strip():
            return FeatureResult(name, "na", "")
        m = pattern.search(text)
        if m:
            return FeatureResult(name, "hit", m.group(0))
        return FeatureResult(name, "miss", "")
    feature.__name__ = name
    return feature


_TRIGGER_RE = re.compile(r"\b(if|when|whenever|before|after|unless)\b", re.I)
_NEGATION_RE = re.compile(r"\b(not|never|no|do not|don't|without)\b", re.I)
_STOP_RE = re.compile(r"\b(stop|halt|block|prevent|do not proceed)\b", re.I)
_ACTOR_RE = re.compile(r"\b(human|me|manager|owner|approver|client)\b", re.I)
_QUANTITY_RE = re.compile(
    r"\b\d+\b|\b(percent|threshold|hour|hours|day|days|week|weeks|minute|minutes)\b", re.I
)
_VERIFY_RE = re.compile(r"\b(verify|check|confirm|validate|test)\b", re.I)
_DEFINITION_RE = re.compile(r"\b(definition|criteria|criterion|rule|standard)\b", re.I)
_ARTIFACT_RE = re.compile(r"\b(brief|report|email|spec|specification|table|document)\b", re.I)
_CAUSAL_RE = re.compile(r"\b(because|so that|in order to|which means)\b", re.I)

has_trigger = _make_regex_feature("has_trigger", _TRIGGER_RE)
has_negation = _make_regex_feature("has_negation", _NEGATION_RE)
has_stop_condition = _make_regex_feature("has_stop_condition", _STOP_RE)
has_actor = _make_regex_feature("has_actor", _ACTOR_RE)
has_quantity = _make_regex_feature("has_quantity", _QUANTITY_RE)
has_verify = _make_regex_feature("has_verify", _VERIFY_RE)
has_definition = _make_regex_feature("has_definition", _DEFINITION_RE)
has_artifact = _make_regex_feature("has_artifact", _ARTIFACT_RE)
has_causal = _make_regex_feature("has_causal", _CAUSAL_RE)

# has_conditional_action is the one feature that is a relationship between
# two words, not membership of one — "if ... then", "approve ... otherwise",
# "escalate ... if" — so it needs its own pair-search instead of a single
# alternation. Each half is still a plain \b-bounded single word searched in
# order, so there is still nothing for backtracking to catch on.
_COND_PAIRS = [
    (re.compile(r"\bif\b", re.I), re.compile(r"\bthen\b", re.I)),
    (re.compile(r"\bapprove\b", re.I), re.compile(r"\botherwise\b", re.I)),
    (re.compile(r"\bescalate\b", re.I), re.compile(r"\bif\b", re.I)),
    (re.compile(r"\bwhen\b", re.I), re.compile(r"\bthen\b", re.I)),
]


def has_conditional_action(text: str) -> FeatureResult:
    if not text or not text.strip():
        return FeatureResult("has_conditional_action", "na", "")
    for first, second in _COND_PAIRS:
        m1 = first.search(text)
        if not m1:
            continue
        m2 = second.search(text, m1.end())
        if m2:
            evidence = text[m1.start():m2.end()].strip()
            return FeatureResult("has_conditional_action", "hit", evidence)
    return FeatureResult("has_conditional_action", "miss", "")


FEATURES: dict[str, Callable[[str], FeatureResult]] = {
    "has_trigger": has_trigger,
    "has_negation": has_negation,
    "has_stop_condition": has_stop_condition,
    "has_actor": has_actor,
    "has_quantity": has_quantity,
    "has_verify": has_verify,
    "has_definition": has_definition,
    "has_conditional_action": has_conditional_action,
    "has_artifact": has_artifact,
    "has_causal": has_causal,
}


# ---------------------------------------------------------------------------
# PER-BLOCK FEATURE MAP
#
# Picked by hand from each block's anchors + why in cordaie_rubrics.json
# (see backend/sixs/aie_map.py's header comment for the same block ->
# concept walk done for the anchor scorer). 3-4 features per block, chosen
# for what a *strong* answer to that specific prompt actually contains —
# not a generic subset of the library.
# ---------------------------------------------------------------------------

BLOCK_FEATURES: dict[str, list[str]] = {
    # m0e0 "cold intent": translate a vague problem into a concrete
    # instruction with a rule -> anchors "if/then/check/flag/stop".
    "m0e0": ["has_trigger", "has_stop_condition", "has_definition", "has_verify"],
    # m0e1 "critique seeded output": blame the missing definition, not the
    # agent -> anchors "had no definition/invented one", "wasn't wrong".
    "m0e1": ["has_definition", "has_negation", "has_causal"],
    # m0e2 "light escalation": when the agent may decide vs. when a human
    # must -> anchors "approve automatically/otherwise ask/escalate if".
    "m0e2": ["has_conditional_action", "has_actor", "has_trigger"],
    # m1e0 "cold intent": define success in checkable terms, including what
    # happens if it fails -> anchors "criteria/under 150 words/if no reply".
    "m1e0": ["has_definition", "has_quantity", "has_trigger", "has_verify"],
    # m1e1 "select + justify": pick the instruction with explicit
    # verification targets -> anchors "checkable/specific items/self-flagging".
    "m1e1": ["has_verify", "has_definition", "has_stop_condition"],
    # m1e2 "live task w/ revision": tie success criteria to a gate that
    # prevents the wrong order -> anchors "threshold/budget/before/exclude".
    "m1e2": ["has_quantity", "has_trigger", "has_negation", "has_stop_condition"],
    # m2e0 "cold intent": set the exact checkpoint trigger for a
    # manager-layer agent -> anchors "if unsure escalate/proceed".
    "m2e0": ["has_conditional_action", "has_trigger", "has_actor"],
    # m2e1 "select + justify": place the checkpoint only where a mistake is
    # expensive/irreversible -> anchors "specific date", justification.
    "m2e1": ["has_quantity", "has_causal", "has_definition"],
    # m2e2 "escalation": stop the chain on externally consequential changes
    # -> anchors "stop/human".
    "m2e2": ["has_stop_condition", "has_actor", "has_conditional_action"],
    # m3e0 "live task w/ revision": revise by naming exact deltas and
    # recurrence rules -> anchors "remove items/not the general thread".
    "m3e0": ["has_negation", "has_quantity", "has_definition"],
    # m3e1 "critique seeded output": update the definition, not only patch
    # one output -> anchors "12 hours/definition/redefine".
    "m3e1": ["has_definition", "has_quantity", "has_negation"],
    # m3e2 "escalation + revision, layered": identify the layer that caused
    # the wrong output -> anchors "coordinator/scope/check what scope".
    "m3e2": ["has_verify", "has_causal", "has_definition"],
}

DELIVER_THRESHOLD = 0.5
STRONG_THRESHOLD = 0.75

# What forward_to_reasoning_model has recorded so far this process. A stub
# store, not a queue — there is nowhere else for the record to go yet.
_ESCALATION_LOG: list[dict] = []

# Durable escalation queue — the catch-net's future inbox. Judges append;
# whatever consumes it (reasoning model, human raters) owns deletion.
ESCALATION_PATH = "/var/lib/cordia/corpus/escalations.jsonl"


def forward_to_reasoning_model(block: str, text: str, judgment: dict) -> dict:
    """Stub for the not-yet-built reasoning-model catch-net.

    Does not call a model and does not change `judgment`. Records that this
    answer fell below the deliver threshold: in-memory for the process, and
    appended to ESCALATION_PATH so the backlog survives restarts. The file
    write is best-effort — a full disk must never break judging.
    """
    record = {
        "block": block,
        "text": text,
        "margin": judgment["margin"],
        "reason": f"margin {judgment['margin']:.2f} below deliver threshold {DELIVER_THRESHOLD}",
    }
    _ESCALATION_LOG.append(record)
    try:
        import json as _json
        import os as _os
        import time as _time
        _os.makedirs(_os.path.dirname(ESCALATION_PATH), exist_ok=True)
        with open(ESCALATION_PATH, "a") as f:
            f.write(_json.dumps({**record, "ts": _time.time()}) + "\n")
    except Exception:
        pass
    return record


def judge_answer(block: str, text: str) -> dict:
    """Run every feature mapped to `block` against `text`.

    Never mutates any score — this is a read-only judgment over the raw
    answer text. Margin below DELIVER_THRESHOLD forwards to the catch-net
    stub as a side effect; the returned frame itself only ever reports what
    was observed.
    """
    if block not in BLOCK_FEATURES:
        raise ValueError(f"no feature map for block {block!r}")

    feature_names = BLOCK_FEATURES[block]
    results = [FEATURES[name](text) for name in feature_names]

    hits = sum(1 for r in results if r.result == "hit")
    total = len(results)
    margin = hits / total if total else 0.0

    if margin >= STRONG_THRESHOLD:
        verdict = "strong"
    elif margin >= DELIVER_THRESHOLD:
        verdict = "partial"
    else:
        verdict = "weak"

    judgment = {
        "block": block,
        "features": [r._asdict() for r in results],
        "hits": hits,
        "total": total,
        "margin": margin,
        "verdict": verdict,
    }

    if margin < DELIVER_THRESHOLD:
        forward_to_reasoning_model(block, text, judgment)

    return judgment


# ---------------------------------------------------------------------------
# CLI self-test
# ---------------------------------------------------------------------------

def _self_test() -> None:
    cases = [
        (
            "strong",
            "m0e0",
            "If a request overlaps with an existing rule, check it against the "
            "definition of a duplicate; if it does not meet that standard, stop "
            "and flag it instead of auto-resolving.",
        ),
        (
            "weak",
            "m0e0",
            "Just handle it and make it better.",
        ),
        (
            "borderline",
            "m0e0",
            "If the request looks unusual, check with someone before proceeding.",
        ),
        (
            "empty",
            "m0e0",
            "",
        ),
    ]

    print(f"{'case':<12} {'block':<6} {'verdict':<9} {'margin':<8} hits/total  features")
    for label, block, text in cases:
        j = judge_answer(block, text)
        feat_summary = ", ".join(f"{f['name']}={f['result']}" for f in j["features"])
        print(
            f"{label:<12} {j['block']:<6} {j['verdict']:<9} {j['margin']:<8.2f} "
            f"{j['hits']}/{j['total']:<8} {feat_summary}"
        )

    print(f"\nescalations recorded: {len(_ESCALATION_LOG)}")
    for rec in _ESCALATION_LOG:
        print(f"  -> {rec['block']}: {rec['reason']}")


if __name__ == "__main__":
    _self_test()
