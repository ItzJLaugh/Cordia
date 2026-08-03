#!/usr/bin/env python3
"""Which question Surveyor asks next. Plain rules, no model, no ML.

The strategy is deliberately boring and readable: walk the priority list, ask
about the highest-value signal we don't have yet, never re-ask something already
answered, and stop once there's enough to build a workspace.

Keeping this rule-based is the point. The LLM's job is to *understand* the
answer; choosing the next question is bookkeeping, and bookkeeping done by a
model is bookkeeping you cannot debug at 2am. If this file ever starts to need
a model to work, delete the feature rather than growing one.
"""

from __future__ import annotations

from . import types

OPENING = ("Welcome. I'm Surveyor. I'll ask a few questions so Cordia can shape "
           "your workspace around how you think and work. Ready to begin?")

# signal -> the question that surfaces it. Conversational, never a test.
QUESTIONS = {
    "domain": "What kind of work are you trying to make easier with AI right now?",
    "role_tendency": ("When you use AI, do you usually feel more like a builder, an "
                      "analyzer, a manager, or someone communicating with people?"),
    "primary_goal": "If Cordia got one thing right for you, what would it be?",
    "graph_preference": ("Do charts, graphs, or system maps help you think, or do they "
                         "usually get in the way?"),
    "drawing_preference": ("Do you ever think better by sketching boxes, arrows, or rough "
                           "diagrams?"),
    "risk_awareness": ("When a mistake could cost money, trust, or safety, where would you "
                       "want the AI to stop and ask you before continuing?"),
    "delegation_style": ("Once you've handed something to an AI, do you like to check every "
                         "step, look once before it's final, or let it run?"),
    "preferred_workspace": ("Would you rather your workspace feel like a clean chat, a visual "
                            "dashboard, a graph or canvas, or a balanced mix?"),
    "verbal_preference": ("Do you tend to think a problem through by talking or writing it "
                          "out?"),
    "visual_preference": "Does seeing something laid out visually help it click for you?",
    "correction_style": ("Imagine an AI gives you an answer that feels wrong but not totally "
                         "useless. What do you usually notice first?"),
    "verification_preference": ("When you get a result back, do you want the evidence behind "
                                "it, a quick answer, or an example to compare against?"),
    "interface_density": ("When building something new, do you prefer a blank canvas, a "
                          "template, a checklist, or a conversation?"),
}

CLOSING = ("Thank you — I'm building your profile now. This is what Cordia will use to "
           "personalise your workspace and recommendations.")


def answered(profile) -> set:
    return {k for k, v in ((profile or {}).get("signals") or {}).items() if v}


def next_signal(profile, asked=()):
    """Highest-priority signal we have neither captured nor already asked about."""
    have = answered(profile)
    asked = set(asked or ())
    for s in types.SIGNAL_PRIORITY:
        if s not in have and s not in asked:
            return s
    return None


def is_done(profile, asked=()) -> bool:
    """Enough signal to build something, or we've run out of things to ask."""
    if len(answered(profile)) >= types.ENOUGH_SIGNALS:
        return True
    return next_signal(profile, asked) is None


def next_question(profile, asked=()):
    """Returns (signal_name, question_text) or (None, closing_line)."""
    if is_done(profile, asked):
        return None, CLOSING
    sig = next_signal(profile, asked)
    if not sig:
        return None, CLOSING
    return sig, QUESTIONS[sig]


def asked_signals(history) -> list:
    """Recover which signals we've already probed from the stored transcript.

    Surveyor is resumable, so the question history has to survive a page reload.
    Message meta carries the signal when we have it; matching on question text
    is the fallback for rows written before meta existed.
    """
    out = []
    text_to_signal = {q: s for s, q in QUESTIONS.items()}
    for m in history or []:
        if m.get("role") != "assistant":
            continue
        sig = (m.get("meta") or {}).get("signal")
        if sig:
            out.append(sig)
            continue
        for q, s in text_to_signal.items():
            if q[:40] in (m.get("content") or ""):
                out.append(s)
                break
    return out
