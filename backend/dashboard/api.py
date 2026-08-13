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


def public_interface(row):
    """A stored interface row, with its definition canonicalised for the
    canvas. Old rows may predate validation; the canvas should never have
    to defend against them."""
    if not isinstance(row, dict):
        return row
    out = dict(row)
    out["definition"] = types.validate_definition(row.get("definition"))
    return out
