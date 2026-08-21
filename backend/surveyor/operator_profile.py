"""Least-privilege, non-scored projection for the Surveyor operator profile."""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from . import artifacts, freeform, identifiers, scenarios, types


_TEXT_LIMIT = 320
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_CONNECTOR_ID = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_CREDENTIAL = re.compile(
    r"(?:^|[^A-Za-z0-9])(?:sk-|pk-|rk-|gh[pousr]_|github_pat_|xox[baprs]-|"
    r"AKIA|(?:api[-_.]?key|access[-_.]?token|token|secret|password|authorization|"
    r"credential)(?:[-_.:=]|\s*=)|bearer\s+|"
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----)", re.IGNORECASE)
_LOCAL_PATH = re.compile(
    r"(?:^|[^A-Za-z0-9_/.])(?:[A-Za-z]:(?:[\\/]|(?=[^\s\\/]))|"
    r"\\\\[^\s]+|(?:file|path)://|\.{1,2}[\\/][^\s]+|"
    r"/(?:tmp|home|Users|var|etc|opt|srv|run|mnt|workspace|Library)(?:/[^\s]*)?|"
    r"/{1,2}(?:[^\s/]+/)+[^\s/]+|"
    r"(?:private|secret|credentials?|keys?)(?:[\\/][^\s]+)+|"
    r"[A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)*[\\/][A-Za-z0-9_-]+\.[A-Za-z0-9]{1,10}(?:[\\/][^\s]*)?|"
    r"/[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,10})", re.IGNORECASE)
_REMOTE_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s<>\"']+")
_BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_STRENGTH = {
    "clear": "clear", "high": "clear",
    "emerging": "emerging", "medium": "emerging",
    "early": "early", "low": "early",
}
_ACTION_TYPES = {"continue_survey", "refine_profile", "create_interface"}


def build(profile, connector_states=None, interfaces=None):
    """Project existing canonical state without adding another state owner."""
    profile = profile if isinstance(profile, dict) else {}
    connector_states = artifacts.normalize_connector_states(
        connector_states if isinstance(connector_states, dict) else {})
    assessment_profile = _validated_assessment_profile(profile)
    assessment = artifacts.assessment_view(assessment_profile, connector_states)
    return {
        "title": "What Cordia currently understands",
        "identifiers": _identifiers(profile.get("identifiers")),
        "understanding": _understanding(assessment.get("understanding")),
        "evidence": _evidence(assessment.get("evidence")),
        "connectors": _connectors(assessment.get("connectors")),
        "still_learning": _still_learning(assessment_profile, connector_states),
        "next_action": _next_action(
            _validated_action_profile(profile), complete=is_complete(profile)),
        "latest_workspace": _latest_workspace(interfaces),
    }


def public_identifiers(items):
    """Allow-list positive display fields for every browser-facing profile."""
    return _identifiers(items)


def next_action(profile):
    """Return the existing forward action after validating legacy profile shapes."""
    profile = profile if isinstance(profile, dict) else {}
    return _next_action(
        _validated_action_profile(profile), complete=is_complete(profile))


def is_complete(profile):
    """Use the canonical three-stage completion rule on bounded known keys only."""
    profile = profile if isinstance(profile, dict) else {}
    raw_scenarios = profile.get("scenarios")
    raw_freeform = profile.get("freeform")
    completion_profile = {
        "questions_answered": profile.get("questions_answered"),
        "signals": types.validate_signals(profile.get("signals")),
        "scenarios": {
            key: value for key, value in (raw_scenarios.items()
                                           if isinstance(raw_scenarios, dict) else [])
            if key in scenarios.IDS
        },
        "freeform": {
            key: value for key, value in (raw_freeform.items()
                                           if isinstance(raw_freeform, dict) else [])
            if key in freeform.KEYS and freeform.clean(value)
        },
    }
    return types.onboarding_complete(completion_profile)


def _validated_assessment_profile(profile):
    evidence = []
    for item in profile.get("evidence") if isinstance(profile.get("evidence"), list) else []:
        if not isinstance(item, dict):
            continue
        summary = item.get("summary")
        confidence = item.get("confidence")
        if isinstance(summary, str) and isinstance(confidence, str):
            evidence.append({"summary": summary, "confidence": confidence})
    return {
        "signals": types.validate_signals(profile.get("signals")),
        "evidence": evidence[:40],
    }


def _validated_action_profile(profile):
    return {
        "signals": types.validate_signals(profile.get("signals")),
        "scores": types.validate_scores(profile.get("scores")),
        "evidence": types.validate_evidence(profile.get("evidence")),
    }


def _identifiers(items):
    output = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        name = _safe_text(item.get("name"), 80)
        meaning = _safe_text(item.get("meaning"), 240)
        use_ai = _safe_text(item.get("use_ai_this_way"), 240)
        strength = _strength(item.get("confidence"))
        if name and meaning and use_ai and strength:
            output.append({
                "name": name,
                "meaning": meaning,
                "use_ai_this_way": use_ai,
                "evidence_strength": strength,
            })
        if len(output) == 3:
            break
    return output


def _understanding(items):
    output = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        label = _safe_text(item.get("label"), 80)
        value = _safe_text(item.get("value"), 240)
        if label and value:
            output.append({"label": label, "value": value})
        if len(output) == 6:
            break
    return output


def _evidence(items):
    output = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        summary = _safe_text(item.get("summary"), 280)
        strength = _strength(item.get("confidence"))
        if summary and strength:
            output.append({"summary": summary, "evidence_strength": strength})
        if len(output) == 6:
            break
    return output


def _connectors(items):
    output = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        connector_id = item.get("id")
        name = _safe_text(item.get("name"), 80)
        status = item.get("status")
        implementation = item.get("implementation_status")
        if (isinstance(connector_id, str) and _CONNECTOR_ID.fullmatch(connector_id) and name and
                status in {"Confirmed by user", "Suggested - not connected"} and
                implementation in {"live", "planned"}):
            output.append({
                "id": connector_id,
                "name": name,
                "status": status,
                "implementation_status": implementation,
            })
        if len(output) == 12:
            break
    return output


def _strength(value):
    return _STRENGTH.get(value) if isinstance(value, str) else None


def _still_learning(profile, connector_states):
    signals = profile.get("signals") if isinstance(profile.get("signals"), dict) else {}
    items = []
    if not _safe_text(signals.get("domain"), 240):
        items.append("Your work domain and operating context")
    if not _safe_text(signals.get("primary_goal"), 240):
        items.append("The first outcome you want Cordia to improve")
    if signals.get("delegation_style") not in {
            "agent_autonomous", "human_checkpoint_before_final", "human_reviews_every_step"}:
        items.append("Where you want a human checkpoint")
    if not _evidence(profile.get("evidence")):
        items.append("Examples in your own words")
    if not artifacts.normalize_connector_states(connector_states):
        items.append("Which systems should be connected")
    return items[:5]


def _next_action(profile, complete=False):
    if complete:
        return {
            "type": "create_interface",
            "label": "Build my workspace",
            "reason": "Your Surveyor intake is complete and ready to shape a workspace.",
        }
    action_profile = dict(profile)
    action_profile["scores"] = (profile.get("scores")
                                if isinstance(profile.get("scores"), dict) else {})
    action_profile["signals"] = (profile.get("signals")
                                 if isinstance(profile.get("signals"), dict) else {})
    action = identifiers.next_best_action(action_profile)
    action_type = action.get("type")
    if action_type == "create_interface":
        action = {
            "type": "refine_profile",
            "label": "Continue with Surveyor",
            "reason": "Finish the bounded intake before Cordia builds your workspace.",
        }
        action_type = action["type"]
    label = _safe_text(action.get("label"), 80)
    reason = _safe_text(action.get("reason"), 240)
    if action_type not in _ACTION_TYPES or not label or not reason:
        return {
            "type": "continue_survey",
            "label": "Talk to Surveyor",
            "reason": "A few answers help Cordia shape the right workspace.",
        }
    return {"type": action_type, "label": label, "reason": reason}


def _latest_workspace(interfaces):
    if not isinstance(interfaces, list) or not interfaces:
        return None
    latest = interfaces[0]
    if not isinstance(latest, dict):
        return None
    workspace_id = latest.get("id")
    if not _safe_identifier(workspace_id):
        return None
    return {
        "id": workspace_id,
        "name": _safe_text(latest.get("name"), 80) or "Workspace",
    }


def _safe_identifier(value):
    return (isinstance(value, str) and bool(_IDENTIFIER.fullmatch(value)) and
            not _is_sensitive(value))


def _safe_text(value, limit=_TEXT_LIMIT):
    if not isinstance(value, str):
        return ""
    value = " ".join(value.split()).strip()
    if not value or len(value) > limit or _is_sensitive(value):
        return ""
    return value


def _is_sensitive(value):
    if _CREDENTIAL.search(value):
        return True
    spans = []
    for match in _REMOTE_URL.finditer(value):
        try:
            remote = match.group(0)
            if _BAD_PERCENT.search(remote):
                return True
            parsed = urlsplit(remote)
            if (parsed.scheme.lower() in {"file", "path"} or not parsed.hostname or
                    parsed.username or parsed.password):
                return True
            details = unquote((parsed.query or "") + " " + (parsed.fragment or ""))
            if _CREDENTIAL.search(details) or _LOCAL_PATH.search(details):
                return True
            spans.append(match.span())
        except (TypeError, ValueError, UnicodeError):
            return True
    remainder = []
    start = 0
    for left, right in spans:
        remainder.append(value[start:left])
        start = right
    remainder.append(value[start:])
    return bool(_LOCAL_PATH.search("".join(remainder)))
