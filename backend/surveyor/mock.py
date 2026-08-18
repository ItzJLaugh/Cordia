#!/usr/bin/env python3
"""Deterministic stand-in for the LLM, so Surveyor works with no model available.

WHY THIS EXISTS
---------------
The hosted model this server calls is currently unreachable in production: the
key file is root-only while the service runs as `cordia`, and the endpoint
returns 403 regardless. Without a fallback, Surveyor would be a chat window that
cannot chat, and the whole builder downstream of it would be untestable.

WHAT IT IS AND IS NOT
---------------------
This is a development and degraded-mode stand-in. It is keyword matching, and
keyword matching is explicitly NOT how Cordia scores anything — that approach
already shipped here once and scored a real user 0/3 for quoting the question
back. It is acceptable here for exactly one reason: this path is a placeholder
that announces itself as one. Every profile built through it is tagged
`"source": "mock"`, and the UI says the model is offline.

If you are reading this while wiring a real model back up: delete nothing, just
make llm.real_available() true. The seam handles the rest.
"""

from __future__ import annotations

import json
import re

from . import question_strategy as qs

# question text -> signal, so the mock knows what was actually being asked
_Q_TO_SIGNAL = {q: s for s, q in qs.QUESTIONS.items()}

_YES = ("yes", "yeah", "yep", "definitely", "absolutely", "love", "help", "helps",
        "a lot", "always", "prefer", "click", "great")
_NO = ("no", "not really", "rarely", "never", "get in the way", "hate", "avoid")

_ROLE = (
    ("analy", "analyzer"), ("build", "prototyper"), ("prototyp", "prototyper"),
    ("manag", "manager"), ("communicat", "human_facing"), ("people", "human_facing"),
    ("technical", "technical_specialist"), ("specialist", "technical_specialist"),
    ("mix", "mixed"),
)
_WORKSPACE = (
    ("canvas", "canvas"), ("graph", "graph_and_chat"), ("dashboard", "dashboard"),
    ("chat", "chat_first"), ("balanc", "balanced"), ("mix", "balanced"),
)
_DELEGATION = (
    ("every step", "human_reviews_every_step"), ("each step", "human_reviews_every_step"),
    ("final", "human_checkpoint_before_final"), ("client-facing", "human_checkpoint_before_final"),
    ("before anything", "human_checkpoint_before_final"),
    ("let it run", "agent_autonomous"), ("autonom", "agent_autonomous"),
    ("trust", "agent_autonomous"),
)
_VERIFICATION = (
    ("evidence", "evidence_first"), ("source", "evidence_first"), ("proof", "evidence_first"),
    ("example", "example_first"), ("quick", "speed_first"), ("fast", "speed_first"),
)
_CORRECTION = (
    ("missing", "specific_missing_detail"), ("detail", "specific_missing_detail"),
    ("compare", "compare_examples"), ("example", "compare_examples"),
    ("step", "ask_steps"), ("rewrite", "rewrite_prompt"), ("rephrase", "rewrite_prompt"),
)
_DENSITY = (
    ("blank", "minimal"), ("minimal", "minimal"), ("clean", "minimal"),
    ("template", "balanced"), ("balanc", "balanced"),
    ("checklist", "detailed"), ("detail", "detailed"),
)


def _first(text, table):
    for needle, value in table:
        if needle in text:
            return value
    return None


def _level(text):
    if any(w in text for w in _NO):
        return "low"
    if any(w in text for w in _YES):
        return "high"
    return "medium"


def _has_saved_runtime_guidance(system):
    """Read only the compiled runtime section; never echo its user-authored text."""
    try:
        blob = (system or "").split("Compiled FDE runtime context:", 1)[1]
        blob = blob.split("Workspace context references:", 1)[0].strip()
        runtime = json.loads(blob)
        mission = str(runtime.get("runtime/fde-tasks.md") or "")
        heading = "## Operating guidance"
        if heading not in mission:
            return False
        operating_guidance = mission.rsplit(heading, 1)[1]
        for line in operating_guidance.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                break
            if stripped.startswith("- Latest correction:"):
                return True
        return False
    except Exception:
        return False


def _extract(question, answer):
    t = (answer or "").lower()
    sig = _Q_TO_SIGNAL.get(question or "")
    out = {}

    if not t.strip():
        return out

    if sig == "domain":
        out["domain"] = answer.strip()[:120]
    elif sig == "primary_goal":
        out["primary_goal"] = answer.strip()[:200]
    elif sig == "role_tendency":
        v = _first(t, _ROLE)
        if v:
            out["role_tendency"] = v
    elif sig in ("graph_preference", "drawing_preference", "visual_preference",
                 "verbal_preference"):
        out[sig] = _level(t)
    elif sig == "risk_awareness":
        out["risk_awareness"] = "high" if len(t) > 12 else "medium"
    elif sig == "preferred_workspace":
        v = _first(t, _WORKSPACE)
        if v:
            out["preferred_workspace"] = v
    elif sig == "delegation_style":
        v = _first(t, _DELEGATION)
        if v:
            out["delegation_style"] = v
    elif sig == "verification_preference":
        v = _first(t, _VERIFICATION)
        if v:
            out["verification_preference"] = v
    elif sig == "correction_style":
        v = _first(t, _CORRECTION)
        if v:
            out["correction_style"] = v
    elif sig == "interface_density":
        v = _first(t, _DENSITY)
        if v:
            out["interface_density"] = v

    # the risk question also reveals a delegation boundary
    if sig == "risk_awareness":
        v = _first(t, _DELEGATION)
        if v:
            out["delegation_style"] = v

    return out


_CRITERION_FOR = {
    "graph_preference": "visual_systems_thinking",
    "drawing_preference": "visual_systems_thinking",
    "visual_preference": "visual_systems_thinking",
    "risk_awareness": "risk_boundary_awareness",
    "domain": "domain_specificity",
    "primary_goal": "intent_clarity",
    "delegation_style": "delegation_readiness",
    "verification_preference": "verification_instinct",
    "correction_style": "gap_detection",
}


def call(system, user, max_tokens=900):
    """Stand in for call_llm(system, user, max_tokens)."""
    # extraction pass — the user payload is the JSON built by prompts.extraction_user
    if "their_answer" in (user or ""):
        try:
            payload = json.loads(user)
        except Exception:
            return json.dumps({"signals": {}, "evidence": []})
        q = payload.get("question_just_asked") or ""
        a = payload.get("their_answer") or ""
        signals = _extract(q, a)
        evidence = []
        for sig in signals:
            crit = _CRITERION_FOR.get(sig)
            if crit:
                evidence.append({"criterion": crit,
                                 "summary": (a or "").strip()[:160],
                                 "confidence": "medium"})
        return json.dumps({"signals": signals, "evidence": evidence})

    # runtime pass — a readable placeholder rather than a fake result
    if "running a user-created Cordia agentic interface" in (system or ""):
        names = []
        try:
            blob = (system or "").split("Interface definition:", 1)[1]
            blob = blob.split("User presentation preferences", 1)[0].strip()
            definition = json.loads(blob)
            names = [a.get("name") for a in (definition.get("agents") or []) if a.get("name")]
        except Exception:
            names = re.findall(r'"name":\s*"([^"]+)"', system or "")[:6]
        steps = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(names)) or "  (no agents defined)"
        guidance = ("\n\nLatest saved guidance was applied to this placeholder run."
                    if _has_saved_runtime_guidance(system) else "")
        return ("[Model offline — placeholder run]\n\n"
                "This interface would run these steps against your input:\n"
                f"{steps}{guidance}\n\n"
                f"Your input was:\n  {(user or '').strip()[:400]}\n\n"
                "Connect a model to get real output. Nothing here was generated by an AI.")

    # surveyor voice — the caller falls back to the scripted question on empty
    return ""
