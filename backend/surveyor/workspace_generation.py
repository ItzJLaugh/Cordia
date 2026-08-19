"""Prepare the first canonical Cordia workspace from Surveyor-owned truth."""

from __future__ import annotations

from copy import deepcopy

from . import adaptation, artifacts, pipeline, workspace_state


def prepare(
    workspace_id: str,
    profile: dict,
    connector_states: dict | None = None,
) -> dict:
    """Return a fixed-name interface definition, state, and compiled artifacts."""
    connector_states = artifacts.normalize_connector_states(connector_states or {})
    bundle = pipeline.compile_artifact_bundle(profile, connector_states)
    defaults = adaptation.builder_defaults(profile)
    definition = {
        "name": "My Workspace",
        "description": "A Cordia workspace shaped from your Surveyor profile.",
        "surface": deepcopy(
            defaults.get("surface") or {"type": "chat", "theme": "minimal"}
        ),
        "agents": deepcopy(defaults.get("agents") or []),
        "tools": deepcopy(defaults.get("tools") or []),
        "workflow": deepcopy(defaults.get("workflow") or {"steps": []}),
    }
    state = workspace_state.from_interface(
        workspace_id, definition, connector_states
    )
    return {
        "id": workspace_id,
        "name": definition["name"],
        "description": definition["description"],
        "definition": definition,
        "workspace": state,
        "artifacts": bundle,
    }
