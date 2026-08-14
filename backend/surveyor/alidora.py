"""Safe, deterministic projection of a canonical workspace for Alidora."""
from __future__ import annotations

from collections import Counter
import re


_ENTITY_TYPES = (
    ("agents", "agent"),
    ("skills", "skill"),
    ("connectors", "connector"),
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_CREDENTIAL = re.compile(
    r"\b(?:api[ _-]?key|access[ _-]?token|token|secret|password|passwd|credential|authorization)\b\s*(?:[:=]|\bis\b)|"
    r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bxox[baprs]-[A-Za-z0-9-]{10,}|"
    r"\bAKIA[0-9A-Z]{16}\b|\bAWS_(?:ACCESS_KEY_ID|SECRET_ACCESS_KEY)\s*=|"
    r"\bgithub_pat_[A-Za-z0-9_]{20,}|\bbearer\s+\S+|"
    r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s@/]+@",
    re.IGNORECASE,
)
_PATH = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|[\\/]{2}[^\\/\s]+[\\/])|"
    r"(?<![A-Za-z0-9:/])/(?:[^/\s]+/)+[^/\s]+|(?:^~[\\/])",
    re.IGNORECASE,
)
_MAX_DISPLAY_TEXT = 240


def map_payload(workspace):
    """Return an allow-listed map payload without workspace-private data."""
    workspace = workspace if isinstance(workspace, dict) else {}
    nodes = _nodes(workspace)
    node_ids = {node["id"] for node in nodes}
    return {
        "workspace": {
            "id": _identifier(workspace.get("id")),
            "title": _display_text(workspace.get("title")),
            "description": _display_text(workspace.get("description")),
        },
        "nodes": nodes,
        "edges": _edges(workspace.get("workflow"), node_ids),
        "summary": {
            "agents": _count(nodes, "agent"),
            "skills": _count(nodes, "skill"),
            "connectors": _count(nodes, "connector"),
            "approval_mode": _approval_mode(workspace.get("permissions")),
        },
    }


def _nodes(workspace):
    nodes = []
    for source_name, kind in _ENTITY_TYPES:
        items = workspace.get(source_name)
        if not isinstance(items, list):
            continue
        identifiers = [
            _identifier(item.get("id"))
            for item in items
            if isinstance(item, dict)
        ]
        duplicates = {identifier for identifier, count in Counter(identifiers).items()
                      if identifier and count > 1}
        for item in items:
            if not isinstance(item, dict):
                continue
            entity_id = _identifier(item.get("id"))
            if not entity_id or entity_id in duplicates:
                continue
            node_id = f"{kind}:{entity_id}"
            raw_label = item.get("name")
            label = _display_text(raw_label)
            if not label and not isinstance(raw_label, str):
                label = entity_id
            nodes.append(
                {
                    "id": node_id,
                    "kind": kind,
                    "label": label,
                    "detail": _display_text(item.get("description")),
                }
            )
    return sorted(nodes, key=lambda node: node["id"])


def _edges(workflow, node_ids):
    if not isinstance(workflow, dict) or not isinstance(workflow.get("steps"), list):
        return []
    edges = set()
    previous_agent = ""
    for step in workflow["steps"]:
        if not isinstance(step, dict):
            previous_agent = ""
            continue
        agent = _agent_endpoint(step, node_ids)
        if not agent:
            previous_agent = ""
            continue
        if previous_agent and previous_agent != agent:
            edges.add((previous_agent, agent))
        for tool in _tool_endpoints(step, node_ids):
            edges.add((agent, tool))
        previous_agent = agent
    return [{"from": source, "to": target} for source, target in sorted(edges)]


def _agent_endpoint(step, node_ids):
    entity_id = _identifier(step.get("agentId"))
    node_id = f"agent:{entity_id}" if entity_id else ""
    return node_id if node_id in node_ids else ""


def _tool_endpoints(step, node_ids):
    tool_ids = step.get("toolIds")
    if not isinstance(tool_ids, list):
        return []
    endpoints = []
    for value in tool_ids:
        entity_id = _identifier(value)
        node_id = f"skill:{entity_id}" if entity_id else ""
        if node_id in node_ids:
            endpoints.append(node_id)
    return endpoints


def _count(nodes, kind):
    return sum(node["kind"] == kind for node in nodes)


def _approval_mode(permissions):
    mode = permissions.get("mode") if isinstance(permissions, dict) else ""
    return mode if mode == "compiled" else ""


def _identifier(value):
    value = value.strip() if isinstance(value, str) else ""
    return value if _IDENTIFIER.fullmatch(value) else ""


def _display_text(value):
    if not isinstance(value, str) or len(value) > _MAX_DISPLAY_TEXT:
        return ""
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return ""
    if _PATH.search(value) or _CREDENTIAL.search(value):
        return ""
    return value
