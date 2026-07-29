#!/usr/bin/env python3
"""6S rubric registry — defined once, as data.

Scoring, storage and (later) the UI all read from here rather than
re-declaring dimensions in each module.

SHADOW MODE. Nothing in this package is shown to learners. cordaie_scoring.py
remains authoritative for every learner-visible number. The 6S scorer writes
to its own tables so that machine scores can be compared against human grades
offline. Promotion to learner-visible happens only after validation clears.

Why the version string says "unvalidated": the structural checks are known to
be unstable under rewording — the offline stability test found 7 of 8 sub-items
swinging past the 5-point threshold, driven entirely by keyword-matching regex
(mean swing 47.9 for exact-regex vs 2.4 for char TF-IDF). Carrying that state
in the version means every stored row self-documents. When validation clears,
this becomes 6s-heuristic-v2 and pre-validation rows stay permanently marked.
"""

from __future__ import annotations

RUBRIC_VERSION = "6s-heuristic-v1-unvalidated"

DIMENSIONS = ["Source", "Success", "Safety", "Steering", "Switch", "Sharpen"]
TIERS = ["foundation", "design", "configuration"]

# sub-item -> (dimension, tier)
ITEM_MAP = {
    "S11_intent_statement":  ("Source",  "foundation"),
    "S21_outcome_statement": ("Success", "foundation"),
    "S22_audience_profile":  ("Success", "foundation"),
    "S23_context_paragraph": ("Success", "foundation"),
    "S31_named_owner":       ("Safety",  "foundation"),
    "S32_constraints_list":  ("Safety",  "design"),
    "S51_exception_table":   ("Switch",  "design"),
    "S65_drift_monitor":     ("Sharpen", "configuration"),
}

# Documented failure patterns. Semantic distance from these is the signal.
FAILURE_ANCHORS = {
    "S11_intent_statement": [
        "This system exists to help the team work more efficiently.",
        "The mandate is to support the business with AI tools.",
    ],
    "S21_outcome_statement": [
        "Write a report on the topic.",
        "Create a summary for the team.",
    ],
    "S22_audience_profile": [
        "The audience will receive the deliverable and review it.",
        "This is sent to the relevant stakeholders as needed.",
    ],
    "S23_context_paragraph": [
        "This matters because it helps the business run more smoothly.",
    ],
    "S31_named_owner": [
        "The team is responsible for this.",
        "Whoever is available will handle it.",
    ],
    "S32_constraints_list": [
        "Agents must not do X.",
        "Do not take action Y without approval.",
    ],
    "S51_exception_table": [
        "If something urgent comes up, someone should look into it.",
    ],
    "S65_drift_monitor": [
        "We will keep an eye on quality over time.",
    ],
}

# Structural regex checks. KNOWN BRITTLE — these match vocabulary, not meaning.
# Do not widen the blend back toward structural until the concept-detection
# rewrite lands and stability_test.py passes.
STRUCTURAL_CHECKS = {
    "S11_intent_statement": [r"\bnot\b.*\bgeneral\b|\bnot\b.*\bnot for\b|specific"],
    "S21_outcome_statement": [r"\b(brief|report|briefing|dashboard|summary)\b",
                              r"\b(so that|delivering|enabling)\b"],
    "S22_audience_profile": [r"\b(partner|manager|client|executive)\b",
                             r"\b(read|act|decide|use|show up)\b"],
    "S23_context_paragraph": [r"\b(because|is not|advantage|table stakes)\b"],
    "S31_named_owner": [r"[A-Z][a-z]+\s[A-Z][a-z]+"],   # case-sensitive on purpose
    "S32_constraints_list": [r"\bnever\b", r"\bunder any circumstances\b|\bregardless of\b"],
    "S51_exception_table": [r"\d+\s*(hour|min)", r"\bdefault\b|\bpause\b|\bescalate\b"],
    "S65_drift_monitor": [r"\bbaseline\b", r"\bthreshold\b", r"\bresponse\b"],
}

# Blend weight per sub-item: how much of the score comes from the STRUCTURAL half.
# The bakeoff showed structural is the fragile signal (swing 47.9) and char
# TF-IDF the stable one (swing 2.4), so the default leans semantic. This is
# "Option B" from the fix instructions — a config change, not a rewrite.
DEFAULT_STRUCTURAL_WEIGHT = 0.25
STRUCTURAL_WEIGHT = {
    # S31 was the only stable structural check (pattern-based, not keyword-based),
    # so it keeps an even split.
    "S31_named_owner": 0.5,
}


def structural_weight(item_name: str) -> float:
    return STRUCTURAL_WEIGHT.get(item_name, DEFAULT_STRUCTURAL_WEIGHT)


class Registry:
    """One scoreable item set: which items exist, where they land in the
    matrix, and what to score them against.

    The scorer takes a Registry rather than importing module globals, so the
    same engine can score the abstract 6S sub-items or a concrete exam's
    blocks (see aie_map.py) without duplicating the matrix logic.
    """

    def __init__(self, name: str, version: str, item_map: dict[str, tuple[str, str]],
                 anchors: dict[str, list[str]], checks: dict[str, list[str]],
                 weights: dict[str, float] | None = None,
                 default_weight: float = DEFAULT_STRUCTURAL_WEIGHT,
                 case_sensitive_items: frozenset[str] = frozenset()):
        self.name = name
        self.version = version
        self.item_map = item_map
        self.anchors = anchors
        self.checks = checks
        self.weights = weights or {}
        self.default_weight = default_weight
        # items whose structural check depends on capitalisation
        self.case_sensitive_items = case_sensitive_items

    def weight(self, item: str) -> float:
        return self.weights.get(item, self.default_weight)

    def coverage(self) -> dict[tuple[str, str], int]:
        cov = {(d, t): 0 for d in DIMENSIONS for t in TIERS}
        for _item, (dim, tier) in self.item_map.items():
            if (dim, tier) in cov:
                cov[(dim, tier)] += 1
        return cov


DEFAULT_REGISTRY = Registry(
    name="6s-abstract",
    version=RUBRIC_VERSION,
    item_map=ITEM_MAP,
    anchors=FAILURE_ANCHORS,
    checks=STRUCTURAL_CHECKS,
    weights=STRUCTURAL_WEIGHT,
    case_sensitive_items=frozenset({"S31_named_owner"}),
)


def implemented_items() -> list[str]:
    return sorted(ITEM_MAP)


def cell_coverage() -> dict[tuple[str, str], int]:
    """How many implemented sub-items land in each (dimension, tier) cell.

    Cells with 0 are not "zero score" — they are not yet measured, and must be
    stored and rendered as null.
    """
    cov = {(d, t): 0 for d in DIMENSIONS for t in TIERS}
    for _item, (dim, tier) in ITEM_MAP.items():
        cov[(dim, tier)] += 1
    return cov
