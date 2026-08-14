"""Safe, deterministic projection of a canonical workspace for Alidora."""
from __future__ import annotations


_ENTITY_TYPES = (
    ("agents", "agent"),
    ("skills", "skill"),
    ("connectors", "connector"),
)


def map_payload(workspace):
    """Return an allow-listed map payload without workspace-private data."""
    workspace = workspace if isinstance(workspace, dict) else {}
    nodes = _nodes(workspace)
    node_ids = {node["id"] for node in nodes}
    return {
        "workspace": {
            "id": _text(workspace.get("id")),
            "title": _text(workspace.get("title")),
            "description": _text(workspace.get("description")),
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
    emitted = set()
    for source_name, kind in _ENTITY_TYPES:
        items = workspace.get(source_name)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            entity_id = _identifier(item.get("id"))
            node_id = f"{kind}:{entity_id}" if entity_id else ""
            if not node_id or node_id in emitted:
                continue
            emitted.add(node_id)
            nodes.append(
                {
                    "id": node_id,
                    "kind": kind,
                    "label": _text(item.get("name")) or entity_id,
                    "detail": _text(item.get("description")),
                }
            )
    return sorted(nodes, key=lambda node: node["id"])


def _edges(workflow, node_ids):
    if not isinstance(workflow, dict) or not isinstance(workflow.get("steps"), list):
        return []
    edges = set()
    for step in workflow["steps"]:
        if not isinstance(step, dict):
            continue
        endpoints = _step_endpoints(step, node_ids)
        for source, target in zip(endpoints, endpoints[1:]):
            if source != target:
                edges.add((source, target))
    return [{"from": source, "to": target} for source, target in sorted(edges)]


def _step_endpoints(step, node_ids):
    endpoints = []
    for kind in ("agent", "skill", "connector"):
        value = step.get(f"{kind}_id", step.get(f"{kind}Id"))
        entity_id = _identifier(value)
        node_id = f"{kind}:{entity_id}" if entity_id else ""
        if node_id in node_ids:
            endpoints.append(node_id)
    return endpoints


def _count(nodes, kind):
    return sum(node["kind"] == kind for node in nodes)


def _approval_mode(permissions):
    return _text(permissions.get("mode")) if isinstance(permissions, dict) else ""


def _identifier(value):
    return value.strip() if isinstance(value, str) else ""


def _text(value):
    return value if isinstance(value, str) else ""
