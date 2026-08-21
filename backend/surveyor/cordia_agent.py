"""Strict Cordia Agent turn envelopes and safe workspace projections."""
from __future__ import annotations

from copy import deepcopy
import json
import re

from . import operator_profile


_ACTION_FIELDS = {
    "speak": {"kind", "speech"},
    "propose_connector": {"kind", "speech", "proposal"},
    "create_artifact": {"kind", "speech", "proposal"},
    "propose_skill": {"kind", "speech", "proposal"},
    "run_approved_skill": {"kind", "speech", "proposal"},
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
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?;])\s*|(?:\r?\n)+")
_COORDINATED_CLAUSE_SPLIT = re.compile(r"\s*,?\s+(?:and|but|or|nor|yet|so)\s+", re.IGNORECASE)
_LEADING_COORDINATOR = re.compile(r"^(?:and|but|or|nor|yet|so)\b\s*", re.IGNORECASE)
_CONDITIONAL_CLAUSE = re.compile(r"^(?:if|when|unless|whether|suppose|assuming)\b", re.IGNORECASE)
_AGENT_COMPLETION = re.compile(
    r"^(?:i(?:['’]ve)?|we(?:['’]ve)?|cordia|(?:the\s+)?(?:agent|assistant))\b"
    r"(?:\s+\w+){0,6}\s+"
    r"(?:connected|completed|approved|executed|ran|run|deployed|created)\b",
    re.IGNORECASE,
)
_BACKEND_STATE = re.compile(
    r"^(?P<subject>.+?)\s+(?:is|was|were|has|have|had)(?:\s+been)?\s+"
    r"(?:(?:fully|successfully|now|already)\s+)*(?P<state>connected|completed|approved|"
    r"executed|ran|run|deployed|created|available)\b(?P<tail>.*)$",
    re.IGNORECASE,
)
_BACKEND_BARE_COMPLETION = re.compile(
    r"^(?P<subject>.+?)\s+(?:(?:fully|successfully|now|already)\s+)*"
    r"(?P<state>connected|completed|approved|executed|ran|run|deployed|created)\b(?P<tail>.*)$",
    re.IGNORECASE,
)
_BACKEND_ENTITY = re.compile(
    r"\b(?:connector|integration|account|service|app|repository|workspace|skill|action(?!\s+plan\b))\b",
    re.IGNORECASE,
)
_EXPLANATORY_BACKEND_STATE = re.compile(r"(?:in the catalog|after approval)", re.IGNORECASE)


class InvalidAgentResponse(ValueError):
    """The configured model did not return one safe, exact action envelope."""


def _known_backend_names(names) -> tuple[str, ...]:
    """Use only bounded, validated connector names rather than guessed proper nouns."""
    result = []
    for name in names if isinstance(names, (list, tuple, set)) else ():
        try:
            clean = _safe_text(name, 160, "unsafe").casefold()
        except ValueError:
            continue
        if clean not in result:
            result.append(clean)
        if len(result) == 30:
            break
    return tuple(result)


def _contains_backend_entity(value: str, known_names: tuple[str, ...]) -> bool:
    lowered = value.casefold()
    return bool(_BACKEND_ENTITY.search(value) or any(
        re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", lowered)
        for name in known_names))


def _false_speak_claim(speech: str, known_connector_names=()) -> bool:
    """Classify each declarative clause; questions and conditions cannot mask others."""
    known_names = _known_backend_names(known_connector_names)
    clauses = (subclause for clause in _CLAUSE_SPLIT.split(speech)
               for subclause in _COORDINATED_CLAUSE_SPLIT.split(clause))
    for clause in clauses:
        clause = _LEADING_COORDINATOR.sub("", clause.strip())
        if not clause or clause.endswith("?") or _CONDITIONAL_CLAUSE.match(clause):
            continue
        bare_clause = clause.rstrip(".!?; ")
        if _AGENT_COMPLETION.match(bare_clause):
            return True
        state = _BACKEND_STATE.match(bare_clause) or _BACKEND_BARE_COMPLETION.match(bare_clause)
        if not state:
            continue
        tail = state.group("tail").strip()
        if state.group("state").casefold() == "available" and _EXPLANATORY_BACKEND_STATE.fullmatch(tail):
            continue
        if (_contains_backend_entity(state.group("subject"), known_names)
                or _contains_backend_entity(tail, known_names)):
            return True
    return False


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
    raw_speech = value["speech"]
    speech = _safe_text(raw_speech, 6000, "Invalid Cordia Agent action.")
    if _false_speak_claim(raw_speech, known_connector_names):
        raise ValueError("Invalid Cordia Agent action.")
    if kind == "speak":
        return {"kind": kind, "speech": speech}
    proposal = value["proposal"]
    _exact_object(proposal, _PROPOSAL_FIELDS[kind], "Invalid Cordia Agent action.")
    out = {"kind": kind, "speech": speech, "proposal": {}}
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
        workspace = context.get("workspace", {}) if isinstance(context, dict) else {}
        names = []
        for connector in workspace.get("connectors", []) if isinstance(workspace, dict) else []:
            if isinstance(connector, dict):
                names.extend((connector.get("id"), connector.get("display_name")))
        return validate_envelope(parsed, known_connector_names=names)
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
    kind, speech = accepted["kind"], accepted["speech"]
    if kind == "speak":
        return state, {"ok": True, "speech": speech, "action": None, "revision": revision}
    if kind == "run_approved_skill":
        return state, {"ok": True, "speech": speech, "revision": revision,
                       "action": {"kind": kind, "state": "approval_required",
                                  "skill_id": accepted["proposal"]["skill_id"]}}
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
    return state, {"ok": True, "speech": speech, "action": public_action, "revision": state["revision"]}
