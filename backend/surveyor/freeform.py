#!/usr/bin/env python3
"""Stage 3: three open questions, stored verbatim.

This is the most valuable data the survey collects and the part we understand
least. The three questions describe someone's *work* rather than their *style*,
and nothing about the answers is predictable from the question.

WHAT WE DO WITH IT
------------------
We surface it. We do not interpret it.

Real understanding of these answers needs a model, and the model is offline. So
the recommendation quotes people back to themselves and light-tags mentions of
a small set of interface primitives, always phrased as "you mentioned" and never
"we determined". A user can check that against their own words in one glance,
so a wrong tag is visible and harmless — which is the opposite of a confident
misreading, and the reason this is deliberately dumb.

The verbatim text is what phase 2 is designed from. The tagging is a courtesy.
"""

from __future__ import annotations

import re

QUESTIONS = [
    ("easier", "Nearly done — in your own words, what would make your job easier?"),
    ("automate", "What's something you do over and over that you'd hand to a machine tomorrow?"),
    ("screen", "If you could design the screen you work on, what would be on it?"),
]

BY_KEY = dict(QUESTIONS)
KEYS = [k for k, _ in QUESTIONS]

MIN_CHARS = 3
MAX_CHARS = 4000

# Interface primitives worth spotting. Substring matching on purpose: this is a
# highlighter, not a classifier, and it is never allowed to decide anything.
PRIMITIVES = {
    "charts":     ("a chart", ["chart", "graph", "plot", "trend", "visual", "dashboard"]),
    "tables":     ("a table", ["table", "spreadsheet", "excel", "grid", "column", "row"]),
    "a board":    ("a board", ["board", "kanban", "pipeline", "backlog", "in progress"]),
    "a calendar": ("a calendar", ["calendar", "schedule", "deadline", "timeline", "due"]),
    "chat":       ("chat", ["chat", "conversation", "ask it", "talk to"]),
    "alerts":     ("alerts", ["alert", "notif", "flag", "warn", "remind", "ping"]),
    "documents":  ("documents", ["document", "report", "write-up", "summary", "draft", "doc"]),
    "checklists": ("checklists", ["checklist", "to-do", "todo", "task list", "steps"]),
}


def next_question(answers):
    for k in KEYS:
        if not (answers or {}).get(k):
            return k, BY_KEY[k]
    return None, None


def clean(text):
    t = " ".join(str(text or "").split())
    return t[:MAX_CHARS] if len(t) >= MIN_CHARS else None


def mentions(answers, keys=None) -> list:
    """Interface primitives the person named, in their own words.

    Returns [{primitive, phrase, quote}] where quote is the fragment of their
    answer that triggered it, so the claim is checkable rather than asserted.

    ``keys`` restricts which answers are scanned. The screen section passes
    ("screen",) because scanning all three tagged "documents" off the word
    "report" in someone's automation answer and then filed it under what to put
    on their screen.
    """
    blob = " ".join((answers or {}).get(k, "") for k in (keys or KEYS)).lower()
    if not blob.strip():
        return []
    found = []
    for name, (phrase, needles) in PRIMITIVES.items():
        for n in needles:
            i = blob.find(n)
            if i == -1:
                continue
            start, end = max(0, i - 34), min(len(blob), i + len(n) + 34)
            quote = blob[start:end].strip()
            found.append({"primitive": name, "phrase": phrase,
                          "quote": ("…" if start else "") + quote + ("…" if end < len(blob) else "")})
            break
    return found


def answered_count(answers) -> int:
    return sum(1 for k in KEYS if (answers or {}).get(k))
