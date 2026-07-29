#!/usr/bin/env python3
"""OFFLINE ONLY — never runs on the VPS, never imported by the live path.

Proves that backend/sixs/textmetrics.py (pure stdlib) computes the same
numbers as scikit-learn's

    TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)) + cosine_similarity

Requires numpy + scikit-learn, which is exactly why it lives in tools/ and not
in backend/ — backend/ is what gets deployed to /opt/cordia/backend.

Usage
    python tools/validate_tfidf_vs_sklearn.py [path-to-prior-work-dir]

If the prior-work directory (the unzipped 6S sandbox files) is supplied, its
real_data.py STRONG/WEAK and stability_test.py STRONG_REPHRASED corpora are
included. Built-in edge cases always run.

Exit code 0 = every comparison within tolerance. Non-zero = divergence.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "backend"))

from sixs import textmetrics                      # noqa: E402
from sixs.rubric import FAILURE_ANCHORS           # noqa: E402

import numpy as np                                # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer   # noqa: E402
from sklearn.metrics.pairwise import cosine_similarity        # noqa: E402

TOL = 1e-9


def sk_mean_similarity(anchors: list[str], text: str) -> float:
    """The reference implementation, lifted verbatim from method_bakeoff.m4."""
    if not anchors:
        return 0.0
    v = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform(anchors + [text])
    return float(np.mean(cosine_similarity(v[-1], v[:-1])[0]))


def sk_ngrams(text: str) -> list[str]:
    an = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).build_analyzer()
    return an(text)


# ---------------------------------------------------------------- edge cases
EDGE_CASES = [
    "",
    " ",
    "a",
    "ab",
    "abc",
    "abcd",
    "I",                                   # single char, shorter than min_n
    "a  b",                                # collapsing double space
    "tabs\tand\nnewlines   everywhere",    # mixed whitespace
    "MiXeD CaSe SHOUTING quietly",         # lowercase folding
    "punctuation, semi; colons: and-dashes!",
    "trailing space ",
    " leading space",
    "número café naïve",                   # non-ascii
    "emoji 🌱 in text",
    "repeated repeated repeated repeated",
    "Never, under any circumstances, escalate past 4 hours.",
    "x" * 400,                             # long single token
]


def collect_corpora(prior: str | None) -> list[tuple[str, str]]:
    """Returns (label, text) pairs to score against every anchor set."""
    corpora: list[tuple[str, str]] = [(f"edge[{i}]", t) for i, t in enumerate(EDGE_CASES)]

    # the anchors themselves are excellent test inputs
    for item, anchors in FAILURE_ANCHORS.items():
        for j, a in enumerate(anchors):
            corpora.append((f"anchor:{item}[{j}]", a))

    if prior and os.path.isdir(prior):
        sys.path.insert(0, prior)
        try:
            import real_data  # type: ignore
            for name in ("STRONG", "WEAK"):
                block = getattr(real_data, name, {})
                for k, v in block.items():
                    corpora.append((f"{name}:{k}", v))
        except Exception as exc:                       # pragma: no cover
            print(f"  ! could not import real_data from {prior}: {exc}")
        try:
            import stability_test  # type: ignore
            block = getattr(stability_test, "STRONG_REPHRASED", {})
            for k, v in block.items():
                corpora.append((f"REPHRASED:{k}", v))
        except Exception as exc:                       # pragma: no cover
            print(f"  ! could not import stability_test from {prior}: {exc}")

    return corpora


def main() -> int:
    prior = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SIXS_PRIOR_WORK")
    corpora = collect_corpora(prior)

    print(f"corpus: {len(corpora)} texts x {len(FAILURE_ANCHORS)} anchor sets")
    print(f"tolerance: {TOL}\n")

    failures = 0
    checks = 0
    worst = 0.0
    worst_where = ""

    # 1. analyzer equivalence — the n-gram lists must match exactly, in order
    print("[1] char_wb analyzer, exact token-sequence match")
    for label, text in corpora:
        ours, theirs = textmetrics.char_wb_ngrams(text), sk_ngrams(text)
        checks += 1
        if ours != theirs:
            failures += 1
            print(f"  FAIL {label}: {len(ours)} grams vs sklearn {len(theirs)}")
            for a, b in zip(ours, theirs):
                if a != b:
                    print(f"       first divergence: {a!r} vs {b!r}")
                    break
    print(f"  {len(corpora)} texts checked\n")

    # 2. end-to-end similarity equivalence
    print("[2] mean cosine similarity vs failure anchors")
    for item, anchors in FAILURE_ANCHORS.items():
        for label, text in corpora:
            ours = textmetrics.mean_similarity_to(anchors, text)
            theirs = sk_mean_similarity(anchors, text)
            delta = abs(ours - theirs)
            checks += 1
            if delta > worst:
                worst, worst_where = delta, f"{item} / {label}"
            if delta > TOL:
                failures += 1
                print(f"  FAIL {item} / {label}: {ours!r} vs {theirs!r} (d={delta:g})")
    print(f"  {len(FAILURE_ANCHORS) * len(corpora)} comparisons\n")

    print(f"total checks : {checks}")
    print(f"failures     : {failures}")
    print(f"max delta    : {worst:g}  ({worst_where})")
    print("\nRESULT:", "PASS — stdlib matches scikit-learn" if failures == 0 else "FAIL")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
