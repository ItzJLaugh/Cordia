#!/usr/bin/env python3
"""Reference micro agent for IRP — Steering dimension."""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/cordia/backend")
from irp.micro_source import MicroAgent, _frame, _unframe, _handle_query

LANE = "steering"


def _classify(text: str) -> dict:
    t = (text or "").lower()
    evidence: list[str] = []
    score = 0.3
    if any(k in t for k in ["align", "policy", "guardrail", "constraint", "must not", "never"]):
        score += 0.3
        evidence.append("steering marker")
    if any(k in t for k in ["if", "unless", "only when", "unless", "condition"]):
        score += 0.15
        evidence.append("conditional marker")
    if any(k in t for k in ["override", "force", "ignore", "skip"]):
        score -= 0.25
        evidence.append("override marker")
    if any(k in t for k in ["vague", "maybe", "probably", "guess", "unclear"]):
        score -= 0.3
        evidence.append("vagueness marker")
    confidence = max(0.05, min(0.98, score))
    if confidence >= 0.75:
        resolution = "steering-explicit"
    elif confidence >= 0.45:
        resolution = "steering-implicit"
    else:
        resolution = "steering-absent"
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
            Path("/var/lib/cordia/irp/micro-steering.pid").unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
