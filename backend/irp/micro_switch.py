#!/usr/bin/env python3
"""Reference micro agent for IRP — Switch dimension."""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/cordia/backend")
from irp.micro_source import MicroAgent, _frame, _unframe, _handle_query

LANE = "switch"


def _classify(text: str) -> dict:
    t = (text or "").lower()
    evidence: list[str] = []
    score = 0.3
    if any(k in t for k in ["switch", "route", "handoff", "transfer", "delegate", "branch"]):
        score += 0.3
        evidence.append("switch marker")
    if any(k in t for k in ["if", "unless", "when", "then", "else"]):
        score += 0.15
        evidence.append("branch marker")
    if any(k in t for k in ["manual", "human", "review", "checkpoint", "approve"]):
        score += 0.15
        evidence.append("human checkpoint marker")
    if any(k in t for k in ["vague", "maybe", "probably", "guess", "unclear"]):
        score -= 0.3
        evidence.append("vagueness marker")
    confidence = max(0.05, min(0.98, score))
    if confidence >= 0.75:
        resolution = "switch-ready"
    elif confidence >= 0.45:
        resolution = "switch-implicit"
    else:
        resolution = "switch-absent"
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
            Path("/var/lib/cordia/irp/micro-switch.pid").unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
