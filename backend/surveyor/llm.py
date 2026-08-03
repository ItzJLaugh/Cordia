#!/usr/bin/env python3
"""The one place that decides whether Surveyor talks to a real model or the mock.

Keeping this decision in a single seam means every caller — extraction, the
Surveyor voice, the interface runtime — degrades the same way, and swapping a
provider later is one file rather than a search-and-replace.

Current production reality, measured rather than assumed:

  * nous_key() reads /root/.hermes/auth.json, mode 600 owned by root, while the
    service runs as User=cordia. The service cannot read it.
  * The endpoint returns HTTP 403 (Cloudflare 1010) even with a valid key.

So the real path is unavailable right now and everything runs on the mock. Both
of those are fixable outside this code (relax the key's ownership to the service
user; sort the upstream account), and when they are, real_available() starts
returning True and nothing else has to change.
"""

from __future__ import annotations

import os

from . import mock


def forced_mock() -> bool:
    """Explicit override, for local development and for the malformed-response
    tests that must not touch the network."""
    return (os.environ.get("SURVEYOR_LLM", "").strip().lower() == "mock")


def real_available(probe=None) -> bool:
    """Whether the hosted model is usable from this process.

    Checks credential *readability* rather than making a network call, because
    this runs on every request and a 90-second timeout is not an acceptable
    price for a health check.
    """
    if forced_mock():
        return False
    if probe is None:
        return False
    try:
        probe()
        return True
    except Exception:
        return False


def caller(real_call, probe=None):
    """Return a call_llm-shaped callable, plus whether it is the real one.

    Falls back to the mock per call as well as up front: a model that is
    reachable at startup and gone by lunchtime should degrade, not 500.
    """
    if not real_available(probe):
        return mock.call, False

    def _call(system, user, max_tokens=900):
        try:
            return real_call(system, user, max_tokens)
        except Exception:
            return mock.call(system, user, max_tokens)

    return _call, True


def status(probe=None) -> dict:
    """For the admin page and the UI's 'model offline' notice."""
    live = real_available(probe)
    return {
        "live": live,
        "mode": "live" if live else "mock",
        "note": ("" if live else
                 "Model offline — Surveyor is running on deterministic placeholder "
                 "responses. Profiles built now are marked as mock."),
    }
