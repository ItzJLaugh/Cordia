#!/usr/bin/env python3
"""OFFLINE ONLY — visualises the scorer's actual geometry.

Every number plotted is computed by backend/sixs, not invented. Needs
matplotlib, so it lives in tools/ and never ships to the VPS.

    python3 tools/plot_score_geometry.py [out.png]
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "backend"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
import numpy as np                                    # noqa: E402

from sixs.aie_map import AIE1_REGISTRY, FAILURE_ANCHORS   # noqa: E402
from sixs.rubric import DIMENSIONS, TIERS                 # noqa: E402
from sixs.scorer import score_submission, semantic_score, structural_score  # noqa: E402
from sixs.textmetrics import mean_similarity_to, tfidf_matrix  # noqa: E402
from aie1_examples import STRONG                                # noqa: E402

INK, ACCENT, WARN, MUTED = "#2e3b22", "#6f8c4c", "#a8462e", "#7c8272"

WEAK = {k: FAILURE_ANCHORS[k][0] for k in STRONG}


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "score_geometry.png")
    blocks = sorted(STRONG)

    fig = plt.figure(figsize=(16, 5.2))
    fig.patch.set_facecolor("white")

    # ---------------- Panel A: the feature space the model lives in --------
    ax = fig.add_subplot(1, 3, 1)
    for label, data, colour, marker in (("strong", STRONG, ACCENT, "o"),
                                        ("weak", WEAK, WARN, "X")):
        xs = [structural_score(b, data[b], AIE1_REGISTRY) for b in blocks]
        ys = [semantic_score(b, data[b], AIE1_REGISTRY) for b in blocks]
        ax.scatter(xs, ys, s=90, c=colour, marker=marker, label=label,
                   edgecolors="white", linewidths=1.2, zorder=3)

    # the CURRENT model: blended = 0.25*structural + 0.75*semantic
    w = 0.25
    for level in (40, 60, 80):
        xs = np.linspace(0, 100, 50)
        ys = (level - w * xs) / (1 - w)
        ax.plot(xs, ys, "--", c=MUTED, lw=1, zorder=1)
        if 0 <= ys[-1] <= 100:
            ax.text(101, ys[-1], f"{level}", color=MUTED, fontsize=8, va="center")

    ax.set_xlabel("structural feature (regex concept classes)")
    ax.set_ylabel("semantic feature (distance from failure anchors)")
    ax.set_title("A · feature space, one point per exam block\n"
                 "dashed = today's FIXED weights (0.25 / 0.75)", fontsize=10, color=INK)
    ax.set_xlim(-5, 105); ax.set_ylim(-5, 105)
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    ax.grid(alpha=.15)

    # ---------------- Panel B: the cosine geometry, actually computed ------
    ax = fig.add_subplot(1, 3, 2)
    item = "m2e2"
    anchors = FAILURE_ANCHORS[item]
    texts = anchors + [WEAK[item], STRONG[item]]
    vecs = tfidf_matrix(texts)

    # project the sparse unit vectors to 2D by their angle to the anchor centroid
    def dot(a, b):
        return sum(v * b[k] for k, v in a.items() if k in b)

    centroid_terms = {}
    for v in vecs[:len(anchors)]:
        for k, val in v.items():
            centroid_terms[k] = centroid_terms.get(k, 0.0) + val / len(anchors)
    n = math.sqrt(sum(v * v for v in centroid_terms.values())) or 1.0
    centroid = {k: v / n for k, v in centroid_terms.items()}

    ang = np.linspace(0, 2 * math.pi, 400)
    ax.plot(np.cos(ang), np.sin(ang), c=MUTED, lw=1, alpha=.5)
    ax.plot([0, 1], [0, 0], c=MUTED, lw=1, ls=":")
    ax.scatter([1], [0], s=140, c=WARN, marker="*", zorder=4)
    ax.text(1.03, .02, "failure-anchor\ncentroid", fontsize=8, color=WARN)

    for label, v, colour, mk in (("an anchor", vecs[0], WARN, "X"),
                                 ("weak answer", vecs[-2], WARN, "o"),
                                 ("strong answer", vecs[-1], ACCENT, "o")):
        cos = max(-1.0, min(1.0, dot(v, centroid)))
        th = math.acos(cos)
        ax.plot([0, math.cos(th)], [0, math.sin(th)], c=colour, lw=1.4, alpha=.8, zorder=2)
        ax.scatter([math.cos(th)], [math.sin(th)], s=90, c=colour, marker=mk,
                   edgecolors="white", linewidths=1.1, zorder=3)
        ax.text(math.cos(th) * 1.09, math.sin(th) * 1.09,
                f"{label}\nscore {100*(1-cos):.0f}", fontsize=8, color=colour,
                ha="left", va="center")

    ax.set_title(f"B · {item}: score IS an angle\n"
                 "score = 100 x (1 - cos θ) from known-bad", fontsize=10, color=INK)
    ax.set_xlim(-.15, 1.5); ax.set_ylim(-.15, 1.25)
    ax.set_aspect("equal"); ax.axis("off")

    # ---------------- Panel C: the tensor slice this produces --------------
    ax = fig.add_subplot(1, 3, 3)
    res = score_submission(STRONG, AIE1_REGISTRY)
    m = np.array([[np.nan if v is None else v for v in row] for row in res["score_matrix"]])
    masked = np.ma.masked_invalid(m)
    cmap = plt.cm.YlGn.copy(); cmap.set_bad("#ece7df")
    im = ax.imshow(masked, cmap=cmap, vmin=0, vmax=100, aspect="auto")
    for i in range(len(DIMENSIONS)):
        for j in range(len(TIERS)):
            v = m[i, j]
            ax.text(j, i, "not\nmeasured" if np.isnan(v) else f"{v:.0f}",
                    ha="center", va="center", fontsize=8,
                    color=MUTED if np.isnan(v) else (INK if v < 65 else "#1e2915"))
    ax.set_xticks(range(len(TIERS)))
    ax.set_xticklabels(["foundation\n(AIE)", "design\n(CAIE)", "configuration\n(CAAIE)"], fontsize=8)
    ax.set_yticks(range(len(DIMENSIONS)))
    ax.set_yticklabels(DIMENSIONS, fontsize=9)
    ax.set_title("C · one submission = one 6x3 slice\n"
                 "N learners x T attempts stacks into a tensor", fontsize=10, color=INK)
    fig.colorbar(im, ax=ax, fraction=.046, pad=.04).set_label("score 0-100", fontsize=8)

    fig.tight_layout()
    fig.savefig(out, dpi=145, facecolor="white")
    print("wrote", out)

    print("\nreal numbers behind panel A:")
    print(f"{'block':7}{'struct(s)':>10}{'sem(s)':>9}{'blend(s)':>10}"
          f"{'struct(w)':>11}{'sem(w)':>9}{'blend(w)':>10}")
    for b in blocks:
        ss, sm = structural_score(b, STRONG[b], AIE1_REGISTRY), semantic_score(b, STRONG[b], AIE1_REGISTRY)
        ws, wm = structural_score(b, WEAK[b], AIE1_REGISTRY), semantic_score(b, WEAK[b], AIE1_REGISTRY)
        print(f"{b:7}{ss:10.1f}{sm:9.1f}{0.25*ss+0.75*sm:10.1f}"
              f"{ws:11.1f}{wm:9.1f}{0.25*ws+0.75*wm:10.1f}")
    print(f"\nfinal composite  strong={res['final_composite']}  "
          f"weak={score_submission(WEAK, AIE1_REGISTRY)['final_composite']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
