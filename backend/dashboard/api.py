#!/usr/bin/env python3
"""Request shaping for the /dashboard/* routes — the pure half.

The route handlers in training_backend.py stay thin adapters (auth guard,
store calls, JSON writer); everything with decision content lives here so
it can be tested without a server, a session, or a database. Same layering
as surveyor: pipeline holds the logic, the route holds the plumbing.

Every function takes plain dicts and returns plain dicts (or an error
string). Nothing here reads the environment, the store, or the network.
"""

from __future__ import annotations

from . import types

# Caps mirror the existing /surveyor/interface route exactly.
_MAX_NAME = 120
_MAX_DESCRIPTION = 600
MAX_RUN_INPUT = 6000


def save_interface_request(body):
    """Shape a save request. Returns ``(error, None)`` or ``(None, cleaned)``.

    ``cleaned['definition']`` is the canonical form from
    ``types.validate_definition`` — the store receives only definitions that
    round-trip, and the response can hand the canonical form straight back
    to the canvas.

    ``id`` handling repeats the hard-won lesson from _surv_save_interface:
    ``str(None)`` is the truthy string ``'None'``, so a JSON null id must
    normalise to "create", never to an edit of an interface literally named
    'None'.
    """
    if not isinstance(body, dict):
        return "invalid request", None
    definition = body.get("definition")
    if not isinstance(definition, dict):
        return "definition must be an object", None
    blockers = types.write_blockers(definition)
    if blockers:
        # Refuse rather than silently canonicalise away well-formed data —
        # the load→save round-trip must never delete what a person stored.
        return "; ".join(blockers[:3]), None
    validated = types.validate_definition(definition)
    name = str(body.get("name", "")).strip()[:_MAX_NAME] \
        or validated.get("name") or "Untitled interface"
    theme = body.get("theme")
    return None, {
        "id": str(body.get("id") or "").strip() or None,
        "name": name,
        "description": str(body.get("description", ""))[:_MAX_DESCRIPTION],
        "definition": validated,
        "theme": theme if isinstance(theme, dict) else None,
    }


def stored_row_conflict(stored_definition):
    """Refusal copy when *overwriting* this stored row would destroy content
    the dashboard cannot represent — even though the incoming payload looks
    clean, because the read path canonicalised before the client ever saw
    the row. Returns None when the overwrite is loss-free.

    This is the second half of the write guard: ``write_blockers`` on the
    request protects against what the client sends; this protects what the
    row already holds (adversarial review proved the first half alone is
    structurally blind on the load→save cycle).
    """
    blockers = types.write_blockers(stored_definition)
    if not blockers:
        return None
    return ("this interface holds content the dashboard cannot edit yet ("
            + "; ".join(blockers[:3]) + ") — open it in the builder instead")


def run_request(body):
    """Shape a run request: ``(error, None)`` or ``(None, {id, input})``."""
    if not isinstance(body, dict):
        return "invalid request", None
    iface_id = str(body.get("id") or "").strip()
    if not iface_id:
        return "id required", None
    prompt = str(body.get("input", ""))[:MAX_RUN_INPUT].strip()
    if not prompt:
        return "input required", None
    return None, {"id": iface_id, "input": prompt}


def skills_search_request(body, profile_framework):
    """Resolve the framework a skills search runs against.

    A client may pass its own framework dict (the canvas already holds
    one); anything else falls back to ``profile_framework`` — the caller
    computes that from the stored profile. retrieve() is defensive, so a
    hostile client framework can only fail to match.
    """
    b = body if isinstance(body, dict) else {}
    fw = b.get("framework")
    if not isinstance(fw, dict):
        fw = profile_framework
    return {"framework": fw, "intent": b.get("intent"),
            "limit": b.get("limit", 8)}


def chat_request(body):
    """Shape a builder-chat turn: ``(error, None)`` or ``(None, {message})``.

    The chat is stateless server-side in v1 — the client holds its own
    transcript, and Step 11's tool-calling model gets its context there.
    The message cap matches the run-input cap; hostile text is the
    model's (or the mock's) problem, never the parser's.
    """
    if not isinstance(body, dict):
        return "invalid request", None
    raw = body.get("message")
    if raw is None:
        # str(None) is the truthy string 'None' — the same trap the save
        # path documents. A JSON null message is an absent message.
        return "message required", None
    message = str(raw)[:MAX_RUN_INPUT].strip()
    if not message:
        return "message required", None
    return None, {"message": message}


def outcome_request(body):
    """Shape a "did this help?" answer: ``(error, None)`` or
    ``(None, {interface_id, worked, description})``.

    ``interface_id`` is required: the verdict must attach to the interface
    the person actually ran — a target of "whatever row is newest" writes
    false pairings into the outcomes dataset the moment someone owns two
    interfaces. ``worked`` must be a real boolean — this is a person's
    explicit yes/no, and coercing a stray string into a verdict would put
    words in their mouth. ``description`` is optional prose, capped like
    the interface description field.
    """
    if not isinstance(body, dict):
        return "invalid request", None
    interface_id = str(body.get("interface_id") or "").strip()
    if not interface_id:
        return "interface_id required", None
    worked = body.get("worked")
    if not isinstance(worked, bool):
        return "worked must be true or false", None
    description = body.get("description")
    if isinstance(description, str):
        description = description.strip()[:_MAX_DESCRIPTION] or None
    else:
        description = None
    return None, {"interface_id": interface_id[:80], "worked": worked,
                  "description": description}


# What the chat says when the model seam returns nothing (the surveyor
# mock answers only the prompts it knows). Same announce-itself discipline
# as mock.py: a placeholder that says it is one, never fake output.
MOCK_CHAT_REPLY = (
    "[Model offline — placeholder reply] Once the model is connected, "
    "Cordia will help you shape this workspace from what you describe "
    "here. The canvas beside this chat is fully usable in the meantime."
)

# When the credential probe says live but the reply is empty, we cannot
# know which of two things happened: the model genuinely replied with
# nothing, or the call failed and the seam's silent mock fallback answered
# "" (llm.caller swallows upstream exceptions). The copy must be true in
# BOTH cases — no "offline" claim, no "the model returned an empty reply"
# claim, and no resend instruction that walks the person into burning
# their rate budget against a dead upstream.
EMPTY_LIVE_REPLY = (
    "[No reply came back] Cordia could not get a model reply for that "
    "message just now. The canvas beside this chat keeps working "
    "either way."
)


def chat_reply(raw, live):
    """The reply the person sees, given what the LLM seam returned.

    Pure so it is testable: the handler stays a thin adapter. Any
    non-string or blank reply becomes a placeholder that announces
    itself. ``live`` is the credential probe, which proves mock mode when
    False but proves nothing when True (the seam falls back to the mock
    per-call on failure) — so the live-side copy commits to nothing
    beyond "no reply arrived".
    """
    if isinstance(raw, str) and raw.strip():
        return raw
    return EMPTY_LIVE_REPLY if live else MOCK_CHAT_REPLY

BUILDER_SYSTEM_PROMPT = (
    "You are Cordia's workspace builder. The person is assembling an "
    "agentic workspace on a visual canvas beside this chat: agents as "
    "cards, ordered steps as connections, human approval points on the "
    "steps that need them. Help them decide what to build — which agents, "
    "which order, where a human should stay in the loop — in plain, "
    "encouraging language. Keep answers short and concrete."
)


def public_interface(row):
    """A stored interface row, with its definition canonicalised for the
    canvas. Old rows may predate validation; the canvas should never have
    to defend against them."""
    if not isinstance(row, dict):
        return row
    out = dict(row)
    out["definition"] = types.validate_definition(row.get("definition"))
    return out
