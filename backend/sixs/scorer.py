#!/usr/bin/env python3
"""6S scorer — standard library only.

Port of the offline sandbox scorer, with three deliberate changes:

  1. The semantic half uses char n-gram TF-IDF (bakeoff method M4) rather than
     the default word-level vectoriser. M4 measured stability 2.4 against
     word-level 4.1 and is markedly more robust to rewording. The stdlib
     implementation is proven equivalent to scikit-learn's by
     tools/validate_tfidf_vs_sklearn.py.

  2. The blend leans semantic rather than splitting 50/50, because the
     structural checks are the unstable half (swing 47.9 vs 2.4).

  3. Scoring is driven by a rubric.Registry rather than module globals, so the
     same engine scores both the abstract 6S sub-items and a concrete exam's
     blocks (aie_map.py) without duplicating the matrix logic.

Uncovered matrix cells are None, never 0.0. A dimension/tier with no
implemented item has *not been measured*; recording it as zero would be a
fabricated score and would poison any later comparison against human grades.
"""

from __future__ import annotations

import re
from typing import Any

from .rubric import DEFAULT_REGISTRY, DIMENSIONS, TIERS, Registry
from .textmetrics import mean_similarity_to

__all__ = ["structural_score", "semantic_score", "score_submission"]


def structural_score(item_name: str, text: str, registry: Registry = DEFAULT_REGISTRY) -> float:
    """Percentage of this item's regex checks that fire."""
    patterns = registry.checks.get(item_name, [])
    if not patterns:
        return 0.0
    # some checks test for capitalisation (a real proper name); folding case
    # there would defeat the check
    flags = 0 if item_name in registry.case_sensitive_items else re.I
    hits = sum(1 for p in patterns if re.search(p, text or "", flags))
    return 100.0 * hits / len(patterns)


def semantic_score(item_name: str, text: str, registry: Registry = DEFAULT_REGISTRY) -> float:
    """Distance from this item's documented failure patterns, 0-100."""
    anchors = registry.anchors.get(item_name, [])
    if not anchors:
        return 50.0          # no anchors defined: contribute nothing directional
    return 100.0 * (1.0 - mean_similarity_to(anchors, text or ""))


def score_submission(submission: dict[str, str],
                     registry: Registry = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Score one submission against `registry`.

    `submission` maps item name -> learner text. Unknown keys are ignored for
    scoring but are never dropped from the stored payload.

    Returns a JSON-serialisable dict:
      rubric_version       str
      sub_scores           {item: {structural, semantic, blended, weight}}
      score_matrix         6x3 nested list, None where not measured
      dimension_composites {dimension: float | None}
      final_composite      float | None
      scorer_signals       which checks fired, for debugging and feature work
    """
    sub_scores: dict[str, dict[str, float]] = {}
    signals: dict[str, Any] = {
        "registry": registry.name,
        "semantic_method": "char_wb_tfidf_3_5_stdlib",
        "items_submitted": sorted(submission),
        "items_scored": [],
        "items_unknown": sorted(set(submission) - set(registry.item_map)),
        "structural_hits": {},
    }

    for item_name, text in submission.items():
        if item_name not in registry.item_map:
            continue
        rule = structural_score(item_name, text, registry)
        sem = semantic_score(item_name, text, registry)
        w = registry.weight(item_name)
        sub_scores[item_name] = {
            "structural": round(rule, 4),
            "semantic": round(sem, 4),
            "blended": round(w * rule + (1.0 - w) * sem, 4),
            "structural_weight": w,
        }
        signals["items_scored"].append(item_name)
        n_checks = len(registry.checks.get(item_name, []))
        signals["structural_hits"][item_name] = {
            "fired": int(round(rule / 100.0 * n_checks)) if n_checks else 0,
            "of": n_checks,
        }
    signals["items_scored"].sort()

    # ---- 6x3 matrix: mean of the items landing in each cell ----
    sums: dict[tuple[int, int], float] = {}
    counts: dict[tuple[int, int], int] = {}
    for item_name, (dim, tier) in registry.item_map.items():
        if item_name not in sub_scores:
            continue
        if dim not in DIMENSIONS or tier not in TIERS:
            continue
        key = (DIMENSIONS.index(dim), TIERS.index(tier))
        sums[key] = sums.get(key, 0.0) + sub_scores[item_name]["blended"]
        counts[key] = counts.get(key, 0) + 1

    matrix: list[list[float | None]] = []
    for d in range(len(DIMENSIONS)):
        row: list[float | None] = []
        for t in range(len(TIERS)):
            n = counts.get((d, t), 0)
            row.append(round(sums[(d, t)] / n, 4) if n else None)   # None, never 0
        matrix.append(row)

    # ---- per-dimension composites: mean of that row's measured cells ----
    dimension_composites: dict[str, float | None] = {}
    for d, dim in enumerate(DIMENSIONS):
        measured = [v for v in matrix[d] if v is not None]
        dimension_composites[dim] = round(sum(measured) / len(measured), 4) if measured else None

    measured_dims = [v for v in dimension_composites.values() if v is not None]
    final_composite = round(sum(measured_dims) / len(measured_dims), 4) if measured_dims else None

    signals["cells_measured"] = sum(1 for r in matrix for v in r if v is not None)
    signals["cells_total"] = len(DIMENSIONS) * len(TIERS)

    return {
        "rubric_version": registry.version,
        "dimensions": DIMENSIONS,
        "tiers": TIERS,
        "sub_scores": sub_scores,
        "score_matrix": matrix,
        "dimension_composites": dimension_composites,
        "final_composite": final_composite,
        "scorer_signals": signals,
    }
