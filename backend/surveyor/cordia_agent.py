"""Strict Cordia Agent turn envelopes and safe workspace projections."""
from __future__ import annotations

from copy import deepcopy
import json
import re
import unicodedata

from . import operator_profile


_ACTION_FIELDS = {
    "speak": {"kind", "speech"},
    "propose_connector": {"kind", "proposal"},
    "create_artifact": {"kind", "proposal"},
    "propose_skill": {"kind", "proposal"},
    "run_approved_skill": {"kind", "proposal"},
}
_PROPOSAL_FIELDS = {
    "propose_connector": {"connector_id", "display_name", "setup_kind", "purpose"},
    "create_artifact": {"artifact_id", "title", "view_mode", "summary"},
    "propose_skill": {"skill_id", "name", "purpose", "connector_id", "operation_id", "artifact_id"},
    "run_approved_skill": {"skill_id"},
}
_ID = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_SAFE_SETUP_KINDS = {"api_key", "openapi", "remote_mcp"}
_SAFE_VIEW_MODES = {"dash", "list", "document"}
_OPERATIONAL_TOKEN = re.compile(
    r"\b(?:connect\w*|configur\w*|setup|setups|run|runs|running|ran|execut\w*|"
    r"deploy\w*|creat\w*|approv\w*|complet\w*|live|enabled|active|ready|available)\b",
    re.IGNORECASE,
)
_OPERATIONAL_CLARIFICATION = (
    "I can discuss that, but workspace status and changes must use a Cordia action."
)


class InvalidAgentResponse(ValueError):
    """The configured model did not return one safe, exact action envelope."""


def _exact_object(value, fields, message):
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(message)


def _safe_text(value, limit, message):
    text = operator_profile._safe_text(value, limit)
    if not text:
        raise ValueError(message)
    return text


def _identifier(value, message, request=False):
    if (not isinstance(value, str) or not ( _REQUEST_ID if request else _ID).fullmatch(value)
            or not operator_profile._safe_identifier(value)):
        raise ValueError(message)
    return value


def validate_turn_request(value: object) -> dict:
    _exact_object(value, {"id", "revision", "message", "idempotency_key"}, "Invalid workspace turn.")
    workspace_id = _identifier(value["id"], "Invalid workspace turn.", request=True)
    revision = value["revision"]
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise ValueError("Invalid workspace turn.")
    message = _safe_text(value["message"], 6000, "Invalid workspace turn.")
    key = _identifier(value["idempotency_key"], "Invalid workspace turn.", request=True)
    return {"id": workspace_id, "revision": revision, "message": message, "idempotency_key": key}


def validate_envelope(value: object, known_connector_names=()) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise ValueError("Invalid Cordia Agent action.")
    kind = value["kind"]
    if kind not in _ACTION_FIELDS:
        raise ValueError("Invalid Cordia Agent action.")
    _exact_object(value, _ACTION_FIELDS[kind], "Invalid Cordia Agent action.")
    if kind == "speak":
        speech = _safe_text(value["speech"], 6000, "Invalid Cordia Agent action.")
        if _OPERATIONAL_TOKEN.search(unicodedata.normalize("NFKC", speech)):
            speech = _OPERATIONAL_CLARIFICATION
        return {"kind": kind, "speech": speech}
    proposal = value["proposal"]
    _exact_object(proposal, _PROPOSAL_FIELDS[kind], "Invalid Cordia Agent action.")
    out = {"kind": kind, "proposal": {}}
    if kind == "propose_connector":
        out["proposal"] = {
            "connector_id": _identifier(proposal["connector_id"], "Invalid Cordia Agent action."),
            "display_name": _safe_text(proposal["display_name"], 160, "Invalid Cordia Agent action."),
            "setup_kind": proposal["setup_kind"],
            "purpose": _safe_text(proposal["purpose"], 600, "Invalid Cordia Agent action."),
        }
        if out["proposal"]["setup_kind"] not in _SAFE_SETUP_KINDS:
            raise ValueError("Invalid Cordia Agent action.")
    elif kind == "create_artifact":
        out["proposal"] = {
            "artifact_id": _identifier(proposal["artifact_id"], "Invalid Cordia Agent action."),
            "title": _safe_text(proposal["title"], 160, "Invalid Cordia Agent action."),
            "view_mode": proposal["view_mode"],
            "summary": _safe_text(proposal["summary"], 600, "Invalid Cordia Agent action."),
        }
        if out["proposal"]["view_mode"] not in _SAFE_VIEW_MODES:
            raise ValueError("Invalid Cordia Agent action.")
    elif kind == "propose_skill":
        out["proposal"] = {
            "skill_id": _identifier(proposal["skill_id"], "Invalid Cordia Agent action."),
            "name": _safe_text(proposal["name"], 160, "Invalid Cordia Agent action."),
            "purpose": _safe_text(proposal["purpose"], 600, "Invalid Cordia Agent action."),
            "connector_id": _identifier(proposal["connector_id"], "Invalid Cordia Agent action."),
            "operation_id": _identifier(proposal["operation_id"], "Invalid Cordia Agent action."),
            "artifact_id": _identifier(proposal["artifact_id"], "Invalid Cordia Agent action."),
        }
    else:
        out["proposal"] = {"skill_id": _identifier(proposal["skill_id"], "Invalid Cordia Agent action.")}
    return out


def public_action_copy(envelope: dict, action: dict | None) -> str:
    """Return fixed public copy from a validated action envelope."""
    del action
    accepted = validate_envelope(envelope)
    kind = accepted["kind"]
    if kind == "propose_connector":
        return f"I prepared a setup card for {accepted['proposal']['display_name']}."
    if kind == "create_artifact":
        return "I prepared a proposed workspace artifact."
    if kind == "propose_skill":
        return "I prepared a proposed skill for review."
    if kind == "run_approved_skill":
        return "This skill requires approval before it can run."
    raise ValueError("Invalid Cordia Agent action.")


def _summary(value, keys):
    if not isinstance(value, dict):
        return None
    out = {}
    for key, limit in keys.items():
        try:
            out[key] = _safe_text(value.get(key), limit, "unsafe")
        except ValueError:
            pass
    return out or None


def build_context(memory: str, workspace: dict, recent_turns: list[dict]) -> dict:
    """Project only approved memory and summary fields into a model context."""
    clean_memory = _safe_text(memory, 12_000, "Invalid compiled memory.") if memory else ""
    state = workspace if isinstance(workspace, dict) else {}
    safe_workspace = {}
    for key, limit in (("title", 160), ("description", 600)):
        try:
            safe_workspace[key] = _safe_text(state.get(key), limit, "unsafe")
        except ValueError:
            safe_workspace[key] = ""
    artifact_source = state.get("windows") if isinstance(state.get("windows"), list) else state.get("artifacts")
    safe_workspace["artifacts"] = [item for item in (
        _summary(value, {"id": 80, "title": 160, "summary": 600})
        for value in (artifact_source if isinstance(artifact_source, list) else [])[:30]
    ) if item]
    safe_workspace["connectors"] = [item for item in (
        _summary(value, {"id": 80, "display_name": 160, "status": 80, "setup_kind": 80,
                         "implementation_status": 80, "lifecycle": 80, "runtime_status": 80})
        for value in (state.get("connectors") if isinstance(state.get("connectors"), list) else [])[:30]
    ) if item]
    safe_workspace["skills"] = [item for item in (
        _summary(value, {"id": 80, "name": 160, "purpose": 600, "connector_id": 80, "operation_id": 80})
        for value in (state.get("skills") if isinstance(state.get("skills"), list) else [])[:30]
    ) if item]
    recent = []
    for turn in (recent_turns if isinstance(recent_turns, list) else [])[-12:]:
        if not isinstance(turn, dict):
            continue
        try:
            recent.append({"user": _safe_text(turn.get("user"), 6000, "unsafe"),
                           "assistant": _safe_text(turn.get("assistant"), 4000, "unsafe")})
        except ValueError:
            continue
    return {"memory": clean_memory, "workspace": safe_workspace, "recent_turns": recent}


def build_system_prompt(context: dict) -> str:
    safe = build_context(context.get("memory", ""), context.get("workspace", {}),
                         context.get("recent_turns", [])) if isinstance(context, dict) else build_context("", {}, [])
    schemas = {kind: {"fields": sorted(fields),
                      "proposal_fields": sorted(_PROPOSAL_FIELDS.get(kind, set()))}
               for kind, fields in _ACTION_FIELDS.items()}
    return ("You are Cordia Agent. Return exactly one JSON action and never claim backend work occurred. "
            "Allowed actions and exact fields: " + json.dumps(schemas, sort_keys=True) + "\n"
            "Compiled memory and safe workspace summaries:\n" + json.dumps(safe, ensure_ascii=False, sort_keys=True))


def run_turn(context: dict, message: str, call_model) -> dict:
    system = build_system_prompt(context)
    raw = call_model(system, message, max_tokens=700)
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise InvalidAgentResponse("Cordia Agent returned an invalid action.") from exc
    try:
        return validate_envelope(parsed)
    except ValueError as exc:
        raise InvalidAgentResponse("Cordia Agent returned an invalid action.") from exc


def apply_proposal(workspace: dict, envelope: dict) -> tuple[dict, dict]:
    accepted = validate_envelope(envelope)
    state = deepcopy(workspace if isinstance(workspace, dict) else {})
    revision = state.get("revision", 0)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        revision = 0
    pending = state.get("pending_actions", [])
    state["pending_actions"] = deepcopy(pending) if isinstance(pending, list) else []
    kind = accepted["kind"]
    if kind == "speak":
        return state, {"ok": True, "speech": accepted["speech"], "action": None, "revision": revision}
    if kind == "run_approved_skill":
        action = {"kind": kind, "state": "approval_required",
                  "skill_id": accepted["proposal"]["skill_id"]}
        return state, {"ok": True, "speech": public_action_copy(accepted, action), "revision": revision,
                       "action": action}
    action = {"kind": kind, **accepted["proposal"]}
    state["pending_actions"].append(action)
    state["revision"] = revision + 1
    if kind == "propose_connector":
        public_action = {"kind": kind, "state": "setup_required",
                         "connector_id": action["connector_id"], "setup_kind": action["setup_kind"]}
    elif kind == "create_artifact":
        public_action = {"kind": kind, "state": "proposal_required", "artifact_id": action["artifact_id"]}
    else:
        public_action = {"kind": kind, "state": "proposal_required", "skill_id": action["skill_id"]}
    return state, {"ok": True, "speech": public_action_copy(accepted, action),
                   "action": public_action, "revision": state["revision"]}
