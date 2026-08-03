#!/usr/bin/env python3
"""Reference micro agent for IRP — Sharpen dimension."""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/cordia/backend")
from irp.micro_source import MicroAgent, _frame, _unframe, _handle_query

LANE = "sharpen"


def _classify(text: str) -> dict:
    t = (text or "").lower()
    evidence: list[str] = []
    score = 0.3
    if any(k in t for k in ["refine", "iterate", "improve", "optimize", "tighten", "sharpen"]):
        score += 0.3
        evidence.append("refinement marker")
    if any(k in t for k in ["feedback", "eval", "score", "metric", "compare"]):
        score += 0.15
        evidence.append("feedback marker")
    if any(k in t for k in ["drift", "noise", "redundant", "duplicate"]):
        score -= 0.25
        evidence.append("drift marker")
    if any(k in t for k in ["vague", "maybe", "probably", "guess", "unclear"]):
        score -= 0.3
        evidence.append("vagueness marker")
    confidence = max(0.05, min(0.98, score))
    if confidence >= 0.75:
        resolution = "refinement-ready"
    elif confidence >= 0.45:
        resolution = "refinement-implicit"
    else:
        resolution = "refinement-absent"
    return {
        "lane": LANE,
        "resolution": resolution,
        "confidence": round(confidence, 3),
        "evidence": evidence,
        "fallback": False,
    }


def main() -> None:
    agent = MicroAgent()
    try:
        agent.run()
    except KeyboardInterrupt:
        agent.alive = False
    finally:
        try:
            Path("/var/lib/cordia/irp/micro-sharpen.pid").unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
