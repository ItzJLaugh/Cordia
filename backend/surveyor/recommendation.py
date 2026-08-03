#!/usr/bin/env python3
"""The assessment at the end: how to set up your AI system, given your answers.

This is the survey's payoff. Everything else in the module exists to make this
paragraph specific to one person rather than generic advice.

It is deliberately *advice*, not configuration. It tells someone what to set up
and why, in words they can act on with any AI tool — not just inside Cordia's
builder. That matters because the recommendation should be worth something even
to a person who never touches the rest of the product.

Same rule as identifiers.py: nothing negative. A recommendation says what to do,
never what the person is bad at. Where we have no signal we say less, rather
than filling the gap with a guess.
"""

from __future__ import annotations

from . import adaptation, identifiers, types

_SURFACE_ADVICE = {
    "canvas": ("Work on a canvas",
               "Give yourself an open space you can arrange — boxes, arrows, things "
               "you move around. Ask the AI to lay out structure there before it "
               "writes anything long."),
    "graph_and_chat": ("Put a map next to the chat",
                       "Keep a diagram of the work beside the conversation. Ask for the "
                       "shape of a plan first, then talk through it."),
    "dashboard": ("Work from a dashboard",
                  "Set up a view where the state of things is visible at a glance, and "
                  "use chat for the exceptions rather than the routine."),
    "chat": ("Keep it a clean chat",
             "One conversation, no panels competing for attention. Put context in the "
             "message rather than in the interface around it."),
}

_DELEGATION_ADVICE = {
    "human_reviews_every_step": (
        "Review each step",
        "Set the agent up to hand back after every step rather than running to "
        "completion. Slower, and it keeps you in the detail where you want to be."),
    "human_checkpoint_before_final": (
        "One checkpoint, just before it's final",
        "Let the agent run the whole task, then stop before anything is sent, "
        "published or shared. That single gate catches most of what matters for "
        "the least interruption."),
    "agent_autonomous": (
        "Let it run, review the result",
        "Give whole tasks rather than steps, and read the output rather than the "
        "process. Keep one hard stop for anything irreversible."),
}


def short_domain(domain):
    """A domain fit to drop mid-sentence, or None.

    People answer "what work are you making easier?" with a whole sentence —
    "I run month-end close at a manufacturer." Truncating that to a word count
    produces "...for I run month-end close at a", which reads like a bug. So we
    only inline the answer when it is already a short noun phrase, and say
    nothing rather than something mangled.
    """
    if not domain:
        return None
    t = " ".join(str(domain).split()).rstrip(".,;!?")
    low = t.lower()
    for lead in ("i ", "we ", "my ", "our ", "i'm ", "im ", "it's "):
        if low.startswith(lead):
            return None
    if len(t.split()) > 5 or len(t) > 48:
        return None
    return t


def _first_identifier_advice(profile):
    return [{"title": i["name"], "body": i["use_ai_this_way"]}
            for i in (profile.get("identifiers") or [])]


def build(profile: dict) -> dict:
    """Return the setup recommendation, or a held state when we know too little."""
    profile = profile or {}
    signals = profile.get("signals") or {}
    complete = types.profile_completeness(profile)

    if not (profile.get("identifiers") or signals):
        return {"ready": False,
                "headline": "Talk to Surveyor first",
                "note": "A few questions and Cordia can tell you how to set your system up.",
                "sections": []}

    defaults = adaptation.builder_defaults(profile)
    surface = (defaults.get("surface") or {}).get("type", "chat")
    sections = []

    title, body = _SURFACE_ADVICE.get(surface, _SURFACE_ADVICE["chat"])
    sections.append({"kind": "surface", "title": title, "body": body, "items": []})

    agents = defaults.get("agents") or []
    if agents:
        sections.append({
            "kind": "agents",
            "title": "Set up these roles",
            "body": ("Rather than one general assistant, give each of these a job and "
                     "its own instruction. They can be separate chats, separate custom "
                     "instructions, or steps in one workflow."),
            "items": [{"title": a["name"], "body": a["instructions"]} for a in agents],
        })

    delegation = signals.get("delegation_style")
    risk = signals.get("risk_awareness")
    if delegation in _DELEGATION_ADVICE:
        title, body = _DELEGATION_ADVICE[delegation]
        if risk == "high":
            body += (" You said you want it to stop before anything irreversible — make "
                     "that the one rule the agent is never allowed to skip.")
        sections.append({"kind": "checkpoints", "title": title, "body": body, "items": []})

    advice = _first_identifier_advice(profile)
    if advice:
        sections.append({
            "kind": "briefing",
            "title": "How to brief it",
            "body": "These follow from how you already work, so they cost you nothing to adopt.",
            "items": advice,
        })

    tools = defaults.get("tools") or []
    if tools:
        sections.append({
            "kind": "tools",
            "title": "Worth wiring up",
            "body": "The capabilities your answers point at most.",
            "items": [{"title": t["name"], "body": ""} for t in tools],
        })

    short = short_domain(signals.get("domain"))
    headline = ("How to set up your AI system for " + short) if short \
        else "How to set up your AI system"

    return {
        "ready": True,
        "headline": headline,
        "note": defaults.get("reason", ""),
        "completeness": int(round(100 * complete)),
        "partial": complete < 1.0,
        "sections": sections,
        "personalized": bool(defaults.get("personalized")),
    }
