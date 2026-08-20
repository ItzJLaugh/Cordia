"""Strict calibration contract and safe compiled workspace memory."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re


SCHEMA_VERSION = "cordia-profile-v1"
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
