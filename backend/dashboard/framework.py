#!/usr/bin/env python3
"""Profile -> dashboard framework: the approved signal mapping, pure and flat.

``framework_from_profile(profile)`` is the contract Step 4 serves at
``GET /dashboard/framework`` and the canvas reads to lay itself out before
the person touches anything. Like ``adaptation.builder_defaults`` it answers
"given what we know, what should this surface look like by default?" — and
like everything in that module, the answer is a default, never a lock.

Deterministic and pure by construction: same profile in, same framework
out — no time, no randomness, no I/O. The only environment read is the
personalization kill switch, resolved through
``surveyor.adaptation.effective_mode`` at call time, exactly like the rest
of the personalization stack:

  * ``PERSONALIZATION_MODE=off``  -> ``GENERIC_FRAMEWORK``, byte-identical
    no matter what the profile says (the kill-switch invariant);
  * ``profile.simple_mode_forced`` -> still personalized — simple *is* the
    normal mode; only ``off`` erases the profile's influence.

Signals are read through ``adaptation._level`` so a stage-2 scenario choice
beats a stage-1 stated answer here exactly as it does everywhere else —
two surfaces disagreeing about "the scenario wins" would personalize the
same person two different ways.

The vocabulary is deliberately free of the never-negative word list: no
value here may ever be "low" (``surveyor.types.NEGATIVE_WORDS`` includes it), which
is why levels read ``graph_first`` / ``balanced`` / ``text_first`` rather
than high/medium/low. ``surveyor.types.assert_positive`` over any framework
must return [] — asserted in tests.
"""

from __future__ import annotations

from surveyor import adaptation
from surveyor.adaptation import GENERIC as _GENERIC_DEFAULTS

# The approved mapping's output vocabulary.
LEAD_SURFACES = ("canvas", "chat", "dashboard")
DIAGRAM_FORWARD = ("graph_first", "balanced", "text_first")
APPROVAL_DENSITY = ("agent_led", "checkpoint_final", "checkpoint_every_step")
NODE_DENSITY = ("minimal", "balanced", "detailed")
ROLE_VIEWS = ("graph", "scaffold", "oversight", "balanced")

# Byte-identical output for every profile when personalization is off.
# The reason line is adaptation.GENERIC's, verbatim — one kill-switch voice.
GENERIC_FRAMEWORK = {
    "personalized": False,
    "lead_surface": "chat",
    "diagram_forward": "balanced",
    "approval_density": "checkpoint_final",
    "node_density": "balanced",
    "role_view": "balanced",
    "verification_nodes": False,
    "reason": _GENERIC_DEFAULTS["reason"],
}

_WORKSPACE_TO_SURFACE = {
    "canvas": "canvas",
    "graph_and_chat": "canvas",     # v1 flagship: graph beside the chat
    "dashboard": "dashboard",
    "chat_first": "chat",
}

_LEVEL_TO_DIAGRAM = {"high": "graph_first", "medium": "balanced", "low": "text_first"}

_DELEGATION_TO_DENSITY = {
    "agent_autonomous": "agent_led",
    "human_checkpoint_before_final": "checkpoint_final",
    "human_reviews_every_step": "checkpoint_every_step",
}

_ROLE_TO_VIEW = {
    "analyzer": "graph",
    "technical_specialist": "graph",
    "prototyper": "scaffold",
    "manager": "oversight",
    "human_facing": "oversight",
}


def _lead_surface(profile) -> str:
    stated = adaptation._level(profile, "preferred_workspace")
    if stated in _WORKSPACE_TO_SURFACE:
        return _WORKSPACE_TO_SURFACE[stated]
    if adaptation._level(profile, "graph_preference") == "high":
        return "canvas"
    if adaptation._level(profile, "visual_preference") == "high":
        return "dashboard"
    return "chat"


def _diagram_forward(profile) -> str:
    for signal in ("graph_preference", "visual_preference"):
        level = adaptation._level(profile, signal)
        if level in _LEVEL_TO_DIAGRAM:
            return _LEVEL_TO_DIAGRAM[level]
    return "balanced"


def _reason(profile, out) -> str:
    bits = []
    stated = adaptation._level(profile, "preferred_workspace")
    if stated:
        bits.append("you asked for " + {
            "canvas": "a canvas",
            "graph_and_chat": "a graph beside the chat",
            "dashboard": "a dashboard",
            "chat_first": "a clean chat",
            "balanced": "a balanced mix",
        }.get(stated, "that layout"))
    elif adaptation._level(profile, "graph_preference") == "high":
        bits.append("you plan in graphs")
    elif adaptation._level(profile, "visual_preference") == "high":
        # visual=high can shape the diagram (graph_first backstop) or the
        # surface (dashboard lead) — either way, say what the person actually
        # showed us, not a graph habit they never stated.
        bits.append("you think visually")
    elif out["diagram_forward"] == "text_first":
        # A real deviation from the generic 'balanced' needs a visible basis:
        # a shaped payload whose reason claims the unshaped standard reads as
        # the product being weird at them.
        bits.append("you plan in prose first")
    role = adaptation._level(profile, "role_tendency")
    if role and role not in ("unknown", "mixed"):
        bits.append(f"you work like {'an' if role[0] in 'aeiou' else 'a'} "
                    f"{role.replace('_', '-')}")
    if out["approval_density"] == "checkpoint_every_step":
        bits.append("you review each step yourself")
    elif out["approval_density"] == "agent_led":
        bits.append("you let the agent run")
    if out["verification_nodes"]:
        bits.append("you check the evidence first")

    if not bits:
        return "Cordia's standard starting point. Talk to Surveyor to shape it around you."
    if len(bits) == 1:
        return f"Shaped because {bits[0]}."
    return "Shaped because " + ", ".join(bits[:-1]) + f", and {bits[-1]}."


def framework_from_profile(profile) -> dict:
    """The approved signal mapping. Pure; returns a fresh dict every call."""
    if adaptation.effective_mode(profile) == "off":
        return dict(GENERIC_FRAMEWORK)

    out = {
        "personalized": True,
        "lead_surface": _lead_surface(profile),
        "diagram_forward": _diagram_forward(profile),
        "approval_density": _DELEGATION_TO_DENSITY.get(
            adaptation._level(profile, "delegation_style"),
            # Cautious end by default, matching the manifest's precedent for
            # a person who never stated a preference.
            "checkpoint_final"),
        "node_density": (lambda d: d if d in NODE_DENSITY else "balanced")(
            adaptation._level(profile, "interface_density")),
        "role_view": _ROLE_TO_VIEW.get(
            adaptation._level(profile, "role_tendency"), "balanced"),
        "verification_nodes": (
            adaptation._level(profile, "verification_preference") == "evidence_first"),
    }
    out["reason"] = _reason(profile, out)
    return out
