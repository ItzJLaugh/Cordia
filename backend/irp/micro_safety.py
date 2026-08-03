#!/usr/bin/env python3
"""Reference micro agent for IRP — Safety dimension."""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/cordia/backend")
from irp.micro_source import MicroAgent, _frame, _unframe, _handle_query

LANE = "safety"


def _classify(text: str) -> dict:
    t = (text or "").lower()
    evidence: list[str] = []
    score = 0.3
    if any(k in t for k in ["compliance", "risk", "audit", "policy", "regulation", "standard"]):
        score += 0.3
        evidence.append("compliance marker")
    if any(k in t for k in ["safe", "secure", "guard", "protect", "fallback", "abort"]):
        score += 0.2
        evidence.append("safety marker")
    if any(k in t for k in ["danger", "unsafe", "expose", "leak", "unsanctioned"]):
        score += 0.2
        evidence.append("danger marker")
    if any(k in t for k in ["vague", "maybe", "probably", "guess", "unclear"]):
        score -= 0.3
        evidence.append("vagueness marker")
    confidence = max(0.05, min(0.98, score))
    if confidence >= 0.75:
        resolution = "safety-anchored"
    elif confidence >= 0.45:
        resolution = "safety-implicit"
    else:
        resolution = "safety-absent"
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
            Path("/var/lib/cordia/irp/micro-safety.pid").unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
