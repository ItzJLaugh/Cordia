#!/usr/bin/env python3
"""Reference micro agent for IRP — Success dimension."""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/cordia/backend")
from irp.micro_source import MicroAgent, _frame, _unframe, _handle_query

LANE = "success"


def _classify(text: str) -> dict:
    t = (text or "").lower()
    evidence: list[str] = []
    score = 0.3
    if any(k in t for k in ["outcome", "measure", "metric", "result", "win", "impact", "value"]):
        score += 0.3
        evidence.append("outcome marker")
    if any(k in t for k in ["criterion", "threshold", "target", "goal"]):
        score += 0.2
        evidence.append("goal marker")
    if any(k in t for k in ["vague", "maybe", "probably", "guess", "unclear"]):
        score -= 0.3
        evidence.append("vagueness marker")
    confidence = max(0.05, min(0.98, score))
    if confidence >= 0.75:
        resolution = "measurable-outcome"
    elif confidence >= 0.45:
        resolution = "outcome-implied"
    else:
        resolution = "outcome-absent"
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
            Path("/var/lib/cordia/irp/micro-success.pid").unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
