"""Strict calibration contract and safe compiled workspace memory."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import time
import ipaddress
import urllib.parse
import urllib.request


SCHEMA_VERSION = "cordia-profile-v1"
_RESULT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_STATE_NONCE = re.compile(r"[A-Za-z0-9_-]{16,128}")
_STATE_TTL_SECONDS = 15 * 60
_SURVEY_HOST = "cordia-survey1.vercel.app"
_SURVEY_PATH = "/survey"
_SAFE_SURVEY_QUERY_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,39}")
_SAFE_SURVEY_QUERY_VALUE = re.compile(r"[A-Za-z0-9._~-]{0,120}")
_TOP_KEYS = {"schema_version", "survey_version", "profile_id", "communication",
             "domains", "personality", "natural_requests", "completed_at"}
_COMMUNICATION_KEYS = {"explicit_implicit", "detail_big_picture",
                       "indirect_direct", "reasoning_before_conclusion",
                       "infer_unstated_context"}
_CREDENTIAL = re.compile(
    r"(?:^|[^A-Za-z0-9])(?:sk-|pk-|rk-|gh[pousr]_|github_pat_|xox[baprs]-|"
    r"AKIA|(?:api[-_.]?key|access[-_.]?token|token|secret|password|authorization|"
    r"credential)(?:[-_.:=]|\s*=)|bearer\s+|"
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----)", re.IGNORECASE)
_LOCAL_PATH = re.compile(
    r"(?:^|[^A-Za-z0-9_/.])(?:[A-Za-z]:(?:[\\/]|(?=[^\s\\/]))|"
    r"\\\\[^\s]+|(?:file|path)://|\.{1,2}[\\/][^\s]+|"
    r"/(?:tmp|home|Users|var|etc|opt|srv|run|mnt|workspace|Library)(?:/[^\s]*)?|"
    r"/{1,2}(?:[^\s/]+/)+[^\s/]+)", re.IGNORECASE)


def _normalized_email(email: object) -> str:
    normalized = email.strip().lower() if isinstance(email, str) else ""
    if not normalized or len(normalized) > 320:
        raise ValueError("profile state owner is invalid")
    return normalized


def _state_key() -> bytes:
    value = os.environ.get("CORDIA_PROFILE_STATE_KEY", "")
    if not value:
        raise ValueError("profile survey state is not configured")
    return value.encode("utf-8")


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("profile survey state is invalid")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("profile survey state is invalid") from exc


def issue_state(email: str, now: int | None = None) -> str:
    """Return a signed, short-lived state bound to the normalized owner."""
    issued = int(time.time() if now is None else now)
    payload = {
        "email": _normalized_email(email),
        "nonce": secrets.token_urlsafe(24),
        "exp": issued + _STATE_TTL_SECONDS,
    }
    encoded = _base64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(_state_key(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_base64url(signature)}"


def verify_state(token: str, authenticated_email: str, now: int | None = None) -> dict:
    """Validate exact state fields, signature, owner binding, and 15-minute expiry."""
    if not isinstance(token, str) or len(token) > 4096 or token.count(".") != 1:
        raise ValueError("profile survey state is invalid")
    encoded, received_signature = token.split(".")
    expected_signature = _base64url(
        hmac.new(_state_key(), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(received_signature, expected_signature):
        raise ValueError("profile survey state is invalid")
    try:
        payload = json.loads(_base64url_decode(encoded))
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("profile survey state is invalid") from exc
    if (not isinstance(payload, dict) or set(payload) != {"email", "nonce", "exp"}
            or not isinstance(payload["email"], str)
            or not isinstance(payload["nonce"], str)
            or not _STATE_NONCE.fullmatch(payload["nonce"])
            or isinstance(payload["exp"], bool) or not isinstance(payload["exp"], int)):
        raise ValueError("profile survey state is invalid")
    current = int(time.time() if now is None else now)
    if (payload["email"] != _normalized_email(authenticated_email)
            or payload["exp"] <= current
            or payload["exp"] > current + _STATE_TTL_SECONDS):
        raise ValueError("profile survey state is invalid")
    return deepcopy(payload)


def _safe_https_endpoint(value: str, resolver) -> str:
    parsed = urllib.parse.urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("profile survey endpoint is invalid") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or parsed.query or (port is not None and port != 443)):
        raise ValueError("profile survey endpoint is invalid")
    host = parsed.hostname.lower()
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(row[4][0])
                         for row in resolver(host, 443, socket.SOCK_STREAM)]
        except (OSError, ValueError) as exc:
            raise ValueError("profile survey endpoint could not be resolved") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("profile survey endpoint is not public")
    return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path.rstrip("/"), "", ""))


class _RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _open_without_redirects(request, timeout):
    return urllib.request.build_opener(_RejectRedirect()).open(request, timeout=timeout)


def fetch_result(result_id: str, opener=None, resolver=socket.getaddrinfo) -> dict:
    """Fetch and validate one result from the configured public HTTPS endpoint."""
    if not isinstance(result_id, str) or not _RESULT_ID.fullmatch(result_id):
        raise ValueError("profile survey result id is invalid")
    base = os.environ.get("CORDIA_PROFILE_RESULT_URL", "").strip()
    if not base:
        raise ValueError("profile survey result endpoint is not configured")
    base = _safe_https_endpoint(base, resolver)
    url = base.rstrip("/") + "/" + urllib.parse.quote(result_id, safe="")
    headers = {"Accept": "application/json"}
    token = os.environ.get("CORDIA_PROFILE_API_TOKEN", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    open_request = opener or _open_without_redirects
    with open_request(request, timeout=10) as response:
        body = response.read(64 * 1024 + 1)
    if len(body) > 64 * 1024:
        raise ValueError("profile survey result is too large")
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("profile survey result is invalid") from exc
    return validate_result(result)


def survey_start_url(email: str) -> str:
    """Build the one permitted survey origin with a fresh, unambiguous state."""
    configured = os.environ.get("CORDIA_PROFILE_SURVEY_URL", "").strip()
    parsed = urllib.parse.urlsplit(configured)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("profile survey is not configured") from exc
    if (parsed.scheme != "https" or parsed.hostname != _SURVEY_HOST or parsed.path != _SURVEY_PATH
            or parsed.username or parsed.password or (port is not None and port != 443)):
        raise ValueError("profile survey is not configured")
    try:
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise ValueError("profile survey is not configured") from exc
    names = set()
    for key, value in query:
        if (key == "state" or key in names or not _SAFE_SURVEY_QUERY_KEY.fullmatch(key)
                or not _SAFE_SURVEY_QUERY_VALUE.fullmatch(value)):
            raise ValueError("profile survey is not configured")
        names.add(key)
    query.append(("state", issue_state(email)))
    return urllib.parse.urlunsplit((
        "https", _SURVEY_HOST, _SURVEY_PATH, urllib.parse.urlencode(query), "",
    ))


def _unsafe_metadata(value: str) -> bool:
    """Keep provider/user metadata out of this compiler's safe input contract."""
    return bool(_CREDENTIAL.search(value) or _LOCAL_PATH.search(value))


def validate_result(value: object) -> dict:
    """Return a detached, exact v1 calibration or raise ``ValueError``."""
    if not isinstance(value, dict) or set(value) != _TOP_KEYS:
        raise ValueError("profile result does not match cordia-profile-v1")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported profile schema")
    communication = value.get("communication")
    if not isinstance(communication, dict) or set(communication) != _COMMUNICATION_KEYS:
        raise ValueError("profile communication result is invalid")
    for key in ("explicit_implicit", "detail_big_picture", "indirect_direct"):
        score = communication.get(key)
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 10:
            raise ValueError("profile communication score is invalid")
    if not all(isinstance(communication[key], bool) for key in
               ("reasoning_before_conclusion", "infer_unstated_context")):
        raise ValueError("profile communication choices are invalid")
    for key, limit in (("survey_version", 80), ("profile_id", 120)):
        field = value.get(key)
        if (not isinstance(field, str) or not re.fullmatch(r"[A-Za-z0-9._:-]+", field)
                or len(field) > limit or _unsafe_metadata(field)):
            raise ValueError(f"profile {key} is invalid")
    domains = value.get("domains")
    if not isinstance(domains, list) or len(domains) > 20:
        raise ValueError("profile domains are invalid")
    for row in domains:
        if (not isinstance(row, dict)
                or set(row) != {"id", "self_rating", "calibration"}
                or not isinstance(row["id"], str)
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", row["id"])
                or _unsafe_metadata(row["id"])
                or isinstance(row["self_rating"], bool)
                or not isinstance(row["self_rating"], int)
                or not 1 <= row["self_rating"] <= 5
                or row["calibration"] not in {"underestimated", "consistent", "overestimated", "unknown"}):
            raise ValueError("profile domain row is invalid")
    personality = value.get("personality")
    if personality != {}:
        raise ValueError("profile personality result is invalid")
    requests = value.get("natural_requests")
    if (not isinstance(requests, list) or len(requests) > 20
            or any(not isinstance(item, str) or not item.strip() or len(item) > 600
                   or _unsafe_metadata(item) for item in requests)):
        raise ValueError("profile natural requests are invalid")
    completed = value.get("completed_at")
    if not isinstance(completed, str) or not completed.endswith("Z"):
        raise ValueError("profile completion time is invalid")
    datetime.fromisoformat(completed[:-1] + "+00:00")
    return deepcopy(value)


def is_calibrated(profile: object) -> bool:
    """Whether a value satisfies the complete, current calibration contract."""
    try:
        validate_result(profile)
    except (TypeError, ValueError):
        return False
    return True


def compile_memory(profile: dict) -> str:
    """Compile allow-listed calibration cues into an inspectable memory artifact."""
    validated = validate_result(profile)
    lines = ["# Workspace Memory", "", "## Communication policy"]
    communication = validated["communication"]
    if communication["reasoning_before_conclusion"]:
        lines.append("- Explain reasoning before conclusions.")
    lines.append("- Label assumptions when inferring unstated context."
                 if communication["infer_unstated_context"]
                 else "- Ask before relying on unstated context.")
    lines.extend(["", "## Domain context"])
    for domain in validated["domains"]:
        label = {"technology_software": "Technology and software"}.get(
            domain["id"], domain["id"].replace("_", " ").capitalize())
        familiarity = {1: "new", 2: "basic", 3: "working", 4: "strong", 5: "advanced"}[
            domain["self_rating"]]
        lines.append(f"- {label}: {familiarity} familiarity.")
    lines.extend(["", "## Observed workspace intent"])
    intent_rules = {
        "dependency": "Understand system dependencies.",
        "risk": "Identify operational risks.",
        "evidence": "Analyze evidence before recommending changes.",
        "connect": "Connect work systems into one visible workspace.",
    }
    request_text = " ".join(validated["natural_requests"]).lower()
    for marker, sentence in intent_rules.items():
        if marker in request_text:
            lines.append("- " + sentence)
    lines.extend(["", "## Evidence", "- Source: Cordia Profile Calibration",
                  f"- Survey version: {validated['survey_version']}",
                  f"- Profile schema: {SCHEMA_VERSION}"])
    return "\n".join(lines) + "\n"
