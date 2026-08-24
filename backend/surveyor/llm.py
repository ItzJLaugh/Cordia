"""Honest availability and call seam for the Cordia Agent model."""
from __future__ import annotations

from . import model_provider


def status() -> dict:
    """Return configured truth without exposing endpoint or credential details."""
    try:
        config = model_provider.configuration()
    except model_provider.ModelUnavailable:
        return {
            "available": False,
            "mode": "unavailable",
            "message": "Cordia Agent is not configured.",
        }
    return {"available": True, "mode": "configured", "model": config["model"]}


def call(system: str, user: str, max_tokens: int = 900) -> str:
    return model_provider.call(system, user, max_tokens=max_tokens)
