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
    system = system or ""
    # Both branches key on the FIXED PREAMBLE of their caller's system
    # prompt — a prefix match, not a contains-check. The runtime prompt
    # interpolates the person's own definition text into its body, so a
    # substring anywhere in the prompt is user-steerable (a saved agent
    # instruction mentioning the extraction phrase hijacked runs into this
    # branch). Position zero is the one place user text can never reach.
    # extraction pass — prompts.EXTRACTION_SYSTEM
    if system.startswith("You read one exchange from a Surveyor conversation"):
        try:
            payload = json.loads(user or "")
        except Exception:
            payload = None
        if not isinstance(payload, dict):
            # a malformed extraction payload must degrade, never raise —
            # the mock-mode caller has no wrapper to absorb an exception
            return json.dumps({"signals": {}, "evidence": []})
        q = str(payload.get("question_just_asked") or "")
        a = str(payload.get("their_answer") or "")
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
    if system.startswith("You are running a user-created Cordia agentic interface"):
        # "These steps" must be the WORKFLOW steps, resolved to agent
        # names — listing the agent declarations here presented a roster
        # the run would never follow. And every claim below is limited to
        # what this code actually established: the old regex fallback
        # scraped tool and workspace names into the step list, and the old
        # note blamed prompt size for parse failures it never measured.
        try:
            blob = system.split("Interface definition:", 1)[1]
            # the template's profile header comes AFTER the definition, so
            # cut at the LAST occurrence — a definition whose own text
            # contains the header phrase must not break the parse
            blob = blob.rsplit("User presentation preferences (soft):", 1)[0].strip()
            parsed = json.loads(blob)
        except Exception:
            # json.dumps output only fails to parse when the prompt-size
            # cap cut it mid-token — the one cause this note may name
            parsed = None
        if parsed is None:
            steps = "  (the definition was too large to list its steps here)"
        else:
            # every displayed fragment is collapsed to one bounded line —
            # a name containing a newline must not fabricate extra
            # numbered steps, and a whitespace-only name is no name
            def _one_line(v):
                return " ".join(str(v).split())[:80] if v is not None else ""

            definition = parsed if isinstance(parsed, dict) else {}
            agents = {}
            raw_agents = definition.get("agents")
            for a in (raw_agents if isinstance(raw_agents, list) else []):
                if isinstance(a, dict) and isinstance(a.get("id"), str):
                    agents[a["id"]] = (_one_line(a.get("name"))
                                       or _one_line(a["id"]) or "unnamed agent")
            wf = definition.get("workflow")
            raw_steps = wf.get("steps") if isinstance(wf, dict) else None
            unreadable = ((wf is not None and not isinstance(wf, dict))
                          or (isinstance(wf, dict) and "steps" in wf
                              and not isinstance(wf.get("steps"), list)))
            lines = []
            skipped = False
            for s in (raw_steps if isinstance(raw_steps, list) else []):
                if isinstance(s, dict):
                    aid = s.get("agentId")
                    who = agents.get(aid) if isinstance(aid, str) else None
                    who = who or _one_line(aid) or "unassigned step"
                    if s.get("requiresApproval"):
                        who += " — pauses for your approval"
                    lines.append(who)
                elif _one_line(s):
                    # legacy rows store bare-string steps; show what is
                    # stored rather than pretending there are no steps
                    lines.append(_one_line(s))
                else:
                    skipped = True
            if unreadable:
                steps = "  (the steps could not be listed here)"
            elif lines:
                steps = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(lines))
                if skipped:
                    steps += "\n  (some steps could not be listed here)"
            elif skipped:
                steps = "  (the steps could not be listed here)"
            else:
                # only claimable when the steps list is genuinely absent
                # or empty — an unreadable shape must not be described as
                # an interface with nothing in it
                steps = "  (no workflow steps defined)"
        return ("[Model offline — placeholder run]\n\n"
                "This interface would run these steps against your input:\n"
                f"{steps}\n\n"
                f"Your input was:\n  {(user or '').strip()[:400]}\n\n"
                "Connect a model to get real output. Nothing here was generated by an AI.")

    # surveyor voice — the caller falls back to the scripted question on empty
    return ""
