#!/usr/bin/env python3
"""Character n-gram TF-IDF + cosine similarity — pure standard library.

This is a faithful reimplementation of:

    TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
    cosine_similarity(...)

which is method M4 from the offline bakeoff (stability 2.4, discrimination
46.4 — passes both thresholds). It exists so the live scoring path keeps the
stdlib-only boundary every other Cordia backend service holds: no numpy, no
scikit-learn, no virtualenv on the VPS.

Equivalence with scikit-learn is not asserted, it is tested. See
tools/validate_tfidf_vs_sklearn.py, which runs both implementations over the
6S corpus and fails if any score diverges by more than 1e-9. That tool is
offline-only and never ships to the server.

Replicated scikit-learn behaviour, precisely:
  * lowercase=True is applied before analysis
  * runs of 2+ whitespace collapse to a single space (``\\s\\s+`` -> " ")
  * each whitespace-delimited word is padded with one leading and one
    trailing space before the sliding window runs
  * a word shorter than n contributes its padded form exactly once, and the
    remaining (larger) n values are skipped for that word
  * raw counts for term frequency (sublinear_tf=False)
  * smooth_idf=True:  idf(t) = ln((1 + N) / (1 + df(t))) + 1
  * L2 row normalisation, so cosine similarity is a plain dot product
"""

from __future__ import annotations

import math
import re
from collections import Counter

__all__ = ["char_wb_ngrams", "tfidf_matrix", "cosine_to_last", "mean_similarity_to"]

_WHITESPACE = re.compile(r"\s\s+")


def char_wb_ngrams(text: str, min_n: int = 3, max_n: int = 5) -> list[str]:
    """Whitespace-sensitive character n-grams, matching sklearn's char_wb."""
    text = _WHITESPACE.sub(" ", (text or "").lower())
    grams: list[str] = []
    for word in text.split():
        w = " " + word + " "
        w_len = len(w)
        for n in range(min_n, max_n + 1):
            offset = 0
            grams.append(w[offset:offset + n])
            while offset + n < w_len:
                offset += 1
                grams.append(w[offset:offset + n])
            # a word shorter than n is counted once, then we stop widening
            if offset == 0:
                break
    return grams


def tfidf_matrix(docs: list[str], min_n: int = 3, max_n: int = 5) -> list[dict[str, float]]:
    """TF-IDF vectors (as sparse term->weight dicts), L2-normalised.

    Fitted on `docs` alone, exactly as the sklearn version refits per call.
    """
    counts = [Counter(char_wb_ngrams(d, min_n, max_n)) for d in docs]

    df: Counter[str] = Counter()
    for c in counts:
        df.update(c.keys())

    n_docs = len(docs)
    idf = {t: math.log((1.0 + n_docs) / (1.0 + d)) + 1.0 for t, d in df.items()}

    vectors: list[dict[str, float]] = []
    for c in counts:
        vec = {t: tf * idf[t] for t, tf in c.items()}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm > 0.0:
            vec = {t: v / norm for t, v in vec.items()}
        vectors.append(vec)
    return vectors


def _dot(a: dict[str, float], b: dict[str, float]) -> float:
    # iterate the smaller vector — the anchors are short, submissions are not
    if len(b) < len(a):
        a, b = b, a
    return sum(w * b[t] for t, w in a.items() if t in b)


def cosine_to_last(docs: list[str], min_n: int = 3, max_n: int = 5) -> list[float]:
    """Cosine similarity of the final document against every earlier one.

    Mirrors ``cosine_similarity(vec[-1], vec[:-1])[0]``. Vectors are already
    L2-normalised, so the dot product *is* the cosine.
    """
    vectors = tfidf_matrix(docs, min_n, max_n)
    target = vectors[-1]
    return [_dot(target, v) for v in vectors[:-1]]


def mean_similarity_to(anchors: list[str], text: str,
                       min_n: int = 3, max_n: int = 5) -> float:
    """Mean cosine similarity between `text` and each anchor. 0.0 if no anchors."""
    if not anchors:
        return 0.0
    sims = cosine_to_last(list(anchors) + [text], min_n, max_n)
    return sum(sims) / len(sims)
