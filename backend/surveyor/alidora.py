"""Safe, deterministic projection of a canonical workspace for Alidora."""
from __future__ import annotations

from collections import Counter
import re

from .artifacts import connector_catalog


_ENTITY_TYPES = (
    ("agents", "agent"),
    ("skills", "skill"),
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_CONSENT = {"confirmed", "suggested"}
_IMPLEMENTATION = {"live", "planned"}
_LIFECYCLE = {"proposed", "needs_handoff", "live", "failed"}
_RUNTIME = {"live", "needs_attention"}
_CONNECTORS = connector_catalog()


def map_payload(workspace):
    """Return an allow-listed map payload without workspace-private data."""
    workspace = workspace if isinstance(workspace, dict) else {}
    nodes, endpoints = _node_projection(workspace)
    return {
        "workspace": {
            "id": _identifier(workspace.get("id")),
            "title": "",
            "description": "",
        },
        "nodes": nodes,
        "edges": _edges(workspace.get("workflow"), endpoints),
        "summary": {
            "agents": _count(nodes, "agent"),
            "skills": _count(nodes, "skill"),
            "connectors": _count(nodes, "connector"),
            "approval_mode": _approval_mode(workspace.get("permissions")),
        },
    }


def _node_projection(workspace):
    nodes = []
    endpoints = {}
    for source_name, kind in _ENTITY_TYPES:
        for index, (entity_id, _item) in enumerate(_unique_entities(workspace.get(source_name)), 1):
            node_id = f"{kind}:{index}"
            endpoints[(kind, entity_id)] = node_id
            nodes.append(
                {
                    "id": node_id,
                    "kind": kind,
                    "label": f"{kind.title()} {index}",
                    "detail": "",
                }
            )

    for entity_id, item in _unique_entities(workspace.get("connectors")):
        status = _connector_status(item)
        manifest = _CONNECTORS.get(entity_id)
        if not status or not manifest:
            continue
        node_id = f"connector:{entity_id}"
        endpoints[("connector", entity_id)] = node_id
        nodes.append(
            {
                "id": node_id,
                "kind": "connector",
                "label": manifest["name"],
                "detail": "",
                "connector_status": status,
            }
        )
    return sorted(nodes, key=lambda node: node["id"]), endpoints


def _unique_entities(items):
    if not isinstance(items, list):
        return []
    entries = [
        (_identifier(item.get("id")), item)
        for item in items
        if isinstance(item, dict)
    ]
    counts = Counter(entity_id for entity_id, _item in entries if entity_id)
    return sorted(
        ((entity_id, item) for entity_id, item in entries if counts[entity_id] == 1),
        key=lambda entry: entry[0],
    )


def _connector_status(item):
    consent = item.get("status")
    implementation = item.get("implementation_status")
    lifecycle = item.get("lifecycle")
    runtime = item.get("runtime_status")
    if consent not in _CONSENT or implementation not in _IMPLEMENTATION or lifecycle not in _LIFECYCLE:
        return None
    if runtime is not None and runtime not in _RUNTIME:
        return None
    return {
        "consent": consent,
        "implementation": implementation,
        "lifecycle": lifecycle,
        "runtime": runtime or "not_observed",
    }


def _edges(workflow, endpoints):
    if not isinstance(workflow, dict) or not isinstance(workflow.get("steps"), list):
        return []
    edges = set()
    previous_agent = ""
    for step in workflow["steps"]:
        if not isinstance(step, dict):
            previous_agent = ""
            continue
        agent = _agent_endpoint(step, endpoints)
        if not agent:
            previous_agent = ""
            continue
        if previous_agent and previous_agent != agent:
            edges.add((previous_agent, agent))
        for tool in _tool_endpoints(step, endpoints):
            edges.add((agent, tool))
        previous_agent = agent
    return [{"from": source, "to": target} for source, target in sorted(edges)]


def _agent_endpoint(step, endpoints):
    entity_id = _identifier(step.get("agentId"))
    return endpoints.get(("agent", entity_id), "")


def _tool_endpoints(step, endpoints):
    tool_ids = step.get("toolIds")
    if not isinstance(tool_ids, list):
        return []
    tools = []
    for value in tool_ids:
        entity_id = _identifier(value)
        node_id = endpoints.get(("skill", entity_id), "")
        if node_id:
            tools.append(node_id)
    return tools


def _count(nodes, kind):
    return sum(node["kind"] == kind for node in nodes)


def _approval_mode(permissions):
    mode = permissions.get("mode") if isinstance(permissions, dict) else ""
    return mode if mode == "compiled" else ""


def _identifier(value):
    value = value.strip() if isinstance(value, str) else ""
    return value if _IDENTIFIER.fullmatch(value) else ""
