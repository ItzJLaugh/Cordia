"""Small, explicit permission gate for early Cordia connector actions."""

from __future__ import annotations


_READ_ACTIONS = {"github.read_repositories"}
_SECRET_ACTIONS = {"github.reveal_token", "github.read_credentials"}
_LOCAL_GIT_READ_ACTIONS = {"desktop.git.status", "desktop.git.wait"}
_LOCAL_GIT_WRITE_ACTIONS = {"desktop.git.pull", "desktop.git.push"}


def decide(action: str, connector_states: dict | None = None) -> dict:
    """Return ALLOW, ASK, or DENY for a typed action without executing it."""
    states = connector_states or {}
    if action in _SECRET_ACTIONS:
        return {"decision": "DENY", "reason": "Cordia never exposes connector credentials."}
    if action in _READ_ACTIONS:
        if states.get("github") == "confirmed":
            return {"decision": "ALLOW", "reason": "Read-only GitHub data is allowed for a confirmed connector."}
        return {"decision": "ASK", "reason": "Confirm GitHub before Cordia reads repository data."}
    if action in _LOCAL_GIT_READ_ACTIONS:
        if states.get("desktop.local_repository") == "confirmed":
            return {"decision": "ALLOW", "reason": "Read-only local Git status is allowed for a confirmed repository."}
        return {"decision": "ASK", "reason": "Confirm a local repository before Cordia reads Git status."}
    if action in _LOCAL_GIT_WRITE_ACTIONS:
        return {"decision": "ASK", "reason": "Local Git pull and push require explicit approval."}
    if action.startswith("github."):
        return {"decision": "ASK", "reason": "GitHub changes require explicit approval."}
    return {"decision": "DENY", "reason": "This capability is not registered."}
