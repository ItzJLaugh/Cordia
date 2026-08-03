#!/usr/bin/env python3
"""Turn one conversational exchange into validated profile observations.

This module is written on the assumption that the LLM *will* misbehave — it will
wrap JSON in a code fence, append an apology, truncate mid-object, invent a
signal name, or return a number where a string belongs. None of that may cost
the user their profile or their request.

So: parse defensively, validate against the allow-lists in types.py, and on any
failure return an empty observation with a reason. The caller keeps the previous
profile and asks the next question. The conversation never breaks.
"""

from __future__ import annotations

import json
import re

from . import prompts, types

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)


def _loads(text):
    """Best-effort JSON out of whatever the model returned.

    Tries the whole string, then the outermost {...}. Anything else is a failure
    and is reported as one rather than guessed at.
    """
    if not isinstance(text, str) or not text.strip():
        return None, "empty response"

    s = _FENCE.sub("", text.strip())
    try:
        v = json.loads(s)
        return (v, None) if isinstance(v, dict) else (None, "not a JSON object")
    except Exception:
        pass

    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        return None, "no JSON object found"
    try:
        v = json.loads(s[start:end + 1])
        return (v, None) if isinstance(v, dict) else (None, "not a JSON object")
    except Exception as e:
        return None, f"unparseable JSON ({type(e).__name__})"


def extract(call_llm, question, answer, recent):
    """Returns (observation, error). observation is always a valid dict.

    ``call_llm`` is injected rather than imported so this stays unit-testable
    without a network — the malformed-response tests drive it directly.
    """
    empty = {"signals": {}, "evidence": []}

    if not (answer or "").strip():
        return empty, "empty answer"

    try:
        raw = call_llm(prompts.extraction_system(),
                       prompts.extraction_user(question, answer, recent),
                       max_tokens=600)
    except Exception as e:
        return empty, f"llm call failed: {type(e).__name__}"

    parsed, err = _loads(raw)
    if err:
        return empty, err

    signals = types.validate_signals(parsed.get("signals"))
    evidence = types.validate_evidence(parsed.get("evidence"))

    # A response that parsed but produced nothing usable is worth logging: it
    # usually means the prompt and the allow-lists have drifted apart.
    if not signals and not evidence:
        return empty, "parsed but no valid signals or evidence"

    return {"signals": signals, "evidence": evidence}, None
