#!/usr/bin/env python3
"""OFFLINE ONLY — shows why the model cannot be fitted yet.

Panel A uses REAL machine scores computed by backend/sixs.
Panels B and C use SIMULATED human grades and are labelled as such on the
figure itself. That data does not exist; the whole point of the picture is
that it doesn't.

    python3 tools/plot_missing_labels.py [out.png]
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "backend"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                    # noqa: E402
import numpy as np                                 # noqa: E402

from sixs.aie_map import AIE1_REGISTRY, FAILURE_ANCHORS   # noqa: E402
from sixs.scorer import score_submission                  # noqa: E402
from aie1_examples import STRONG                           # noqa: E402  (shared examples)

INK, ACCENT, WARN, MUTED = "#2e3b22", "#6f8c4c", "#a8462e", "#7c8272"
WEAK = {k: FAILURE_ANCHORS[k][0] for k in STRONG}
BLOCKS = sorted(STRONG)


def real_machine_scores() -> list[float]:
    """A genuine spread: k strong answers mixed with (12-k) weak ones."""
    out = []
    for k in range(len(BLOCKS) + 1):
        sub = {b: (STRONG[b] if i < k else WEAK[b]) for i, b in enumerate(BLOCKS)}
        out.append(score_submission(sub, AIE1_REGISTRY)["final_composite"])
    return out


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "missing_labels.png")
    x_real = np.array(real_machine_scores())

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.4))
    fig.patch.set_facecolor("white")

    # ---------------------------------------------- A: today
    ax = axes[0]
    ax.axhspan(0, 100, color="#f2ece2", zorder=0)
    ax.scatter(x_real, np.zeros_like(x_real), s=95, c=ACCENT, marker="o",
               edgecolors="white", linewidths=1.2, zorder=4, clip_on=False)
    ax.text(np.mean(x_real), 52,
            "NO DATA\n\nnothing has a vertical position,\nso no line can be fitted",
            ha="center", va="center", fontsize=12, color=WARN, weight="bold")
    ax.annotate("", xy=(x_real.min(), 3), xytext=(x_real.min(), 20),
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.2))
    ax.text(x_real.min() + 1, 22, "every point is stuck on the floor",
            fontsize=8.5, color=MUTED)
    ax.set_xlabel("X — machine score (REAL, computed by backend/sixs)")
    ax.set_ylabel("Y — human grade (0-100)")
    ax.set_title("A · TODAY\n13 real machine scores, 0 human grades",
                 fontsize=11, color=INK)
    ax.set_xlim(40, 100); ax.set_ylim(0, 100)
    ax.grid(alpha=.15)

    # ---------------------------------------------- B: with graders (SIMULATED)
    rng = np.random.default_rng(11)
    n = 50
    x_sim = rng.uniform(45, 95, n)
    truth = 1.55 * x_sim - 48 + rng.normal(0, 7, n)        # machine is compressed + biased
    truth = np.clip(truth, 0, 100)
    gA = np.clip(truth + rng.normal(0, 6, n), 0, 100)
    gB = np.clip(truth + rng.normal(0, 6, n), 0, 100)
    y_sim = (gA + gB) / 2

    ax = axes[1]
    ax.scatter(x_sim, gA, s=34, c=ACCENT, alpha=.55, label="grader A", edgecolors="none")
    ax.scatter(x_sim, gB, s=34, c="#a8913f", alpha=.55, label="grader B", edgecolors="none")
    b1, b0 = np.polyfit(x_sim, y_sim, 1)
    xs = np.linspace(40, 100, 40)
    ax.plot(xs, b1 * xs + b0, c=INK, lw=2, label=f"fitted: y = {b1:.2f}x {b0:+.0f}")
    r = np.corrcoef(x_sim, y_sim)[0, 1]
    agree = np.corrcoef(gA, gB)[0, 1]
    ax.text(43, 92, f"r(machine, human) = {r:.2f}\nr(grader A, grader B) = {agree:.2f}",
            fontsize=9, color=INK,
            bbox=dict(boxstyle="round,pad=.4", fc="white", ec=MUTED, lw=.8))
    ax.text(0.5, 0.03, "SIMULATED — this data does not exist yet",
            transform=ax.transAxes, ha="center", fontsize=10, color=WARN, weight="bold")
    ax.set_xlabel("X — machine score")
    ax.set_ylabel("Y — human grade")
    ax.set_title("B · WITH ~50 DOUBLE-GRADED SUBMISSIONS\nthe axis exists, so a line exists",
                 fontsize=11, color=INK)
    ax.set_xlim(40, 100); ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    ax.grid(alpha=.15)

    # ---------------------------------------------- C: what the fit buys you
    ax = axes[2]
    raw_lo, raw_hi = x_real.min(), x_real.max()
    ax.barh([1.0], [raw_hi - raw_lo], left=[raw_lo], height=.34, color=MUTED, alpha=.55)
    ax.text(raw_lo - 1, 1.0, "raw machine", ha="right", va="center", fontsize=9, color=INK)
    ax.text((raw_lo + raw_hi) / 2, 1.0, f"{raw_lo:.0f} – {raw_hi:.0f}",
            ha="center", va="center", fontsize=9, color="white", weight="bold")

    cal_lo, cal_hi = b1 * raw_lo + b0, b1 * raw_hi + b0
    ax.barh([0.4], [cal_hi - cal_lo], left=[cal_lo], height=.34, color=ACCENT)
    ax.text(cal_lo - 1, 0.4, "after fitting", ha="right", va="center", fontsize=9, color=INK)
    ax.text((cal_lo + cal_hi) / 2, 0.4, f"{cal_lo:.0f} – {cal_hi:.0f}",
            ha="center", va="center", fontsize=9, color="white", weight="bold")

    ax.text(50, 1.62,
            "The machine already separates good from bad —\n"
            "it just reports it inside a narrow band.\n"
            "Fitting stretches it onto a scale that means something.",
            fontsize=9.5, color=INK, va="center")
    ax.text(0.5, 0.03, "stretch factor is SIMULATED until real grades exist",
            transform=ax.transAxes, ha="center", fontsize=9, color=WARN)
    ax.set_xlim(0, 105); ax.set_ylim(0.05, 2.0)
    ax.set_yticks([]); ax.set_xlabel("score scale (0-100)")
    ax.set_title("C · WHAT THE FIT ACTUALLY BUYS\ncalibration, not new information",
                 fontsize=11, color=INK)
    ax.grid(axis="x", alpha=.15)

    fig.tight_layout()
    fig.savefig(out, dpi=145, facecolor="white")
    print("wrote", out)
    print("\nREAL machine composites (panel A x-values):")
    print("  " + "  ".join(f"{v:.1f}" for v in x_real))
    print(f"  span: {x_real.min():.1f} to {x_real.max():.1f}  "
          f"= {x_real.max() - x_real.min():.1f} points of a 100-point scale")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
