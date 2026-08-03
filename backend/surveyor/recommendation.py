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

from . import adaptation, freeform, identifiers, types

# One sentence each. These are read on a results page next to three identifier
# cards and five other sections; at 25-30 words apiece the page stopped being
# scannable and became something to wade through.
_SURFACE_ADVICE = {
    "canvas": ("Work on a canvas",
               "An open space you arrange yourself. Ask for structure before prose."),
    "graph_and_chat": ("Put a map next to the chat",
                       "A diagram beside the conversation. Ask for the shape first."),
    "dashboard": ("Work from a dashboard",
                  "State visible at a glance. Chat for the exceptions, not the routine."),
    "chat": ("Keep it a clean chat",
             "One conversation. Context in the message, not the interface."),
}

_DELEGATION_ADVICE = {
    "human_reviews_every_step": (
        "Review each step",
        "It hands back after every step. Slower, keeps you in the detail."),
    "human_checkpoint_before_final": (
        "One checkpoint, just before it's final",
        "It runs the whole task, then stops before anything goes out."),
    "agent_autonomous": (
        "Let it run, review the result",
        "Whole tasks, not steps. One hard stop for anything irreversible."),
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


def _tension_line(t) -> str:
    """State the fact, then offer the reading as a possibility.

    The fact is true whether or not the scenario is well written. The reading
    might not be — a badly worded situation would otherwise let measurement
    error masquerade as a claim about someone's character — so it is always
    hedged and always followed by something concrete to do.
    """
    from . import question_strategy as qs
    from . import scenarios as scn

    stated = qs.label_for(t["dimension"], t["stated"])
    revealed = next((l for v, l in scn.BY_ID[t["scenario"]]["options"]
                     if v == t["revealed"]), t["revealed"])
    fact = 'Earlier you said “%s”. In the situation, you chose “%s”.' % (stated, revealed)
    parts = [fact]
    if t.get("reading"):
        parts.append(t["reading"])
    if t.get("do"):
        parts.append("Either way: " + t["do"])
    return " ".join(parts)


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
    # Scenario choices override stated answers on any dimension they cross-check.
    from . import scenarios as _scn
    effective = _scn.effective(profile)
    sections = []

    title, body = _SURFACE_ADVICE.get(surface, _SURFACE_ADVICE["chat"])
    sections.append({"kind": "surface", "title": title, "body": body, "items": []})

    agents = defaults.get("agents") or []
    if agents:
        sections.append({
            "kind": "agents",
            "title": "Set up these roles",
            "body": "Give each a job and its own instruction.",
            "items": [{"title": a["name"], "body": a["instructions"]} for a in agents],
        })

    delegation = effective.get("delegation_style")
    risk = effective.get("risk_awareness")
    if delegation in _DELEGATION_ADVICE:
        title, body = _DELEGATION_ADVICE[delegation]
        if risk == "high":
            body += " Never let it skip that on anything irreversible."
        sections.append({"kind": "checkpoints", "title": title, "body": body, "items": []})

    advice = _first_identifier_advice(profile)
    if advice:
        sections.append({
            "kind": "briefing",
            "title": "How to brief it",
            "body": "These follow from how you already work.",
            "items": advice,
        })

    # What the scenarios revealed that stage 1 didn't say. This is the only
    # section here that can tell someone something they didn't tell us, so it
    # goes above the composed advice rather than as a footnote.
    tensions = [t for t in (profile.get("tensions") or []) if not t.get("agreed")]
    if tensions:
        sections.insert(1, {
            "kind": "tension",
            "title": "Where your answers pulled in different directions",
            "body": "An observation, not a verdict — you'll know if it lands.",
            "items": [{
                "title": t.get("name") or "A difference worth noticing",
                "body": _tension_line(t),
            } for t in tensions],
        })

    # Their own words about the work. Quoted, never interpreted — see freeform.py.
    ff = profile.get("freeform") or {}
    if ff.get("automate"):
        sections.append({
            "kind": "automation", "title": "Start with what you already named",
            "body": "Your own answer — so you already know it's worth doing.",
            "items": [{"title": "In your words", "body": ff["automate"]}],
        })

    seen = freeform.mentions(ff, keys=("screen",))
    if seen or ff.get("screen"):
        items = [{"title": m["phrase"].capitalize(), "body": "you mentioned: “%s”" % m["quote"]}
                 for m in seen]
        sections.append({
            "kind": "screen", "title": "What to put on the screen",
            "body": "Things you named — check them against what you meant.",
            "items": items or [{"title": "In your words", "body": ff.get("screen", "")}],
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
