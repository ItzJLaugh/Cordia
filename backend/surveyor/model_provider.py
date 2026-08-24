"""Bounded OpenAI-compatible model provider for the Cordia Agent."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

PUBLIC_UNAVAILABLE = "Cordia Agent is not configured."
PUBLIC_INVALID_CONFIGURATION = "Cordia Agent provider configuration is invalid."
PUBLIC_FAILURE = "Cordia Agent could not complete that request."
MAX_PROMPT_CHARS = 12_000
MAX_RESPONSE_BYTES = 256 * 1024
MAX_TOKENS = 1_200


class ModelUnavailable(RuntimeError):
    """Raised before an upstream request when the model is not configured."""


class ModelFailure(RuntimeError):
    """Raised for every upstream, transport, or response-shape failure."""


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urllib.parse.urlsplit(url)
    return (parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port or 443)


def configuration(environment=None) -> dict:
    """Return only an explicitly configured, HTTPS OpenAI-compatible endpoint."""
    environment = environment if environment is not None else os.environ
    base_url = str(environment.get("LLM_BASE_URL") or "").strip()
    model = str(environment.get("LLM_MODEL") or "").strip()
    key = str(environment.get("LLM_KEY") or "").strip()
    if not base_url or not model or not key:
        raise ModelUnavailable(PUBLIC_UNAVAILABLE)
    try:
        parsed = urllib.parse.urlsplit(base_url)
        parsed.port  # validate a numeric port if one was supplied
        valid = bool(parsed.scheme.lower() == "https" and parsed.netloc and parsed.hostname
                     and not parsed.username and not parsed.password)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ModelUnavailable(PUBLIC_INVALID_CONFIGURATION)
    return {"base_url": base_url, "model": model, "key": key}


def status(environment=None) -> dict:
    """Return public-safe configuration readiness without contacting OpenAI."""
    try:
        config = configuration(environment)
    except ModelUnavailable:
        return {"provider": "openai", "configured": False, "model": ""}
    return {"provider": "openai", "configured": True,
            "model": str(config["model"])[:120]}


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow HTTPS redirects only when they stay on the configured origin."""
    def __init__(self, expected_origin):
        super().__init__()
        self._expected_origin = expected_origin

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            same_origin = _origin(newurl) == self._expected_origin
        except (TypeError, ValueError):
            same_origin = False
        if not same_origin:
            raise ModelFailure(PUBLIC_FAILURE)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _bounded_prompt(value: str) -> str:
    if not isinstance(value, str):
        raise ModelFailure(PUBLIC_FAILURE)
    return value[:MAX_PROMPT_CHARS]


def _bounded_max_tokens(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelFailure(PUBLIC_FAILURE)
    return max(1, min(value, MAX_TOKENS))


def call(system: str, user: str, max_tokens: int = 900,
         opener=urllib.request.urlopen) -> str:
    """Call the configured model without exposing upstream details publicly."""
    config = configuration()
    try:
        body = json.dumps({
            "model": config["model"],
            "messages": [
                {"role": "system", "content": _bounded_prompt(system)},
                {"role": "user", "content": _bounded_prompt(user)},
            ],
            "max_tokens": _bounded_max_tokens(max_tokens),
            "temperature": 0.4,
        }).encode("utf-8")
        request = urllib.request.Request(config["base_url"], data=body, headers={
            "Content-Type": "application/json",
            "User-Agent": "cordia-training/1.0",
            "Authorization": "Bearer " + config["key"],
        })
        expected_origin = _origin(config["base_url"])
        request_opener = opener
        if opener is urllib.request.urlopen:
            request_opener = urllib.request.build_opener(
                _SameOriginRedirectHandler(expected_origin)).open
        with request_opener(request, timeout=30) as response:
            if _origin(response.geturl()) != expected_origin:
                raise ModelFailure(PUBLIC_FAILURE)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ModelFailure(PUBLIC_FAILURE)
        content = json.loads(raw.decode("utf-8"))["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ModelFailure(PUBLIC_FAILURE)
        return content
    except ModelFailure:
        raise
    except Exception:
        raise ModelFailure(PUBLIC_FAILURE) from None
