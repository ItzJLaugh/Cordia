"""Compile Surveyor evidence into inspectable personal-FDE Markdown artifacts.

This module deliberately contains no connector credentials, network calls, or
LLM inference. It is the small, deterministic boundary between Surveyor's
working hypothesis and the runtime context Cordia will later execute against.
"""

from __future__ import annotations

from copy import deepcopy


_CONNECTOR_CATALOG = {
    "google_drive": {"name": "Google Drive", "category": "storage",
                     "setup_modes": ["oauth", "mcp"],
                     "runtime_transports": ["direct_api", "mcp"]},
    "gmail": {"name": "Gmail", "category": "communication",
              "setup_modes": ["oauth", "mcp"],
              "runtime_transports": ["direct_api", "mcp"]},
    "google_calendar": {"name": "Google Calendar", "category": "calendar",
                        "setup_modes": ["oauth", "mcp"],
                        "runtime_transports": ["direct_api", "mcp"]},
    "notion": {"name": "Notion", "category": "knowledge",
               "setup_modes": ["oauth", "api_key", "mcp"],
               "runtime_transports": ["direct_api", "mcp"]},
    "slack": {"name": "Slack", "category": "communication",
              "setup_modes": ["oauth", "mcp"],
              "runtime_transports": ["direct_api", "mcp"]},
    "discord": {"name": "Discord", "category": "communication",
                "setup_modes": ["oauth", "api_key", "mcp"],
                "runtime_transports": ["direct_api", "mcp"]},
    "github": {"name": "GitHub", "category": "development",
               "setup_modes": ["oauth", "api_key", "mcp"],
               "runtime_transports": ["direct_api", "mcp", "local_bridge"]},
    "gitlab": {"name": "GitLab", "category": "development",
               "setup_modes": ["oauth", "api_key", "mcp"],
               "runtime_transports": ["direct_api", "mcp", "local_bridge"]},
    "linear": {"name": "Linear", "category": "project_management",
               "setup_modes": ["oauth", "api_key", "mcp"],
               "runtime_transports": ["direct_api", "mcp"]},
    "jira": {"name": "Jira", "category": "project_management",
             "setup_modes": ["oauth", "api_key", "mcp"],
             "runtime_transports": ["direct_api", "mcp"]},
    "sharepoint": {"name": "SharePoint", "category": "storage",
                   "setup_modes": ["oauth", "mcp"],
                   "runtime_transports": ["direct_api", "mcp"]},
    "onedrive": {"name": "OneDrive", "category": "storage",
                 "setup_modes": ["oauth", "mcp"],
                 "runtime_transports": ["direct_api", "mcp"]},
    "dropbox": {"name": "Dropbox", "category": "storage",
                "setup_modes": ["oauth", "api_key", "mcp"],
                "runtime_transports": ["direct_api", "mcp"]},
    "box": {"name": "Box", "category": "storage",
            "setup_modes": ["oauth", "api_key", "mcp"],
            "runtime_transports": ["direct_api", "mcp"]},
    "microsoft_teams": {"name": "Microsoft Teams", "category": "communication",
                        "setup_modes": ["oauth", "mcp"],
                        "runtime_transports": ["direct_api", "mcp"]},
    "asana": {"name": "Asana", "category": "project_management",
              "setup_modes": ["oauth", "api_key", "mcp"],
              "runtime_transports": ["direct_api", "mcp"]},
    "clickup": {"name": "ClickUp", "category": "project_management",
                "setup_modes": ["oauth", "api_key", "mcp"],
                "runtime_transports": ["direct_api", "mcp"]},
    "azure_boards": {"name": "Azure Boards", "category": "project_management",
                     "setup_modes": ["oauth", "api_key", "mcp"],
                     "runtime_transports": ["direct_api", "mcp"]},
    "basecamp": {"name": "Basecamp", "category": "project_management",
                 "setup_modes": ["oauth", "api_key", "mcp"],
                 "runtime_transports": ["direct_api", "mcp"]},
    "airtable": {"name": "Airtable", "category": "data",
                 "setup_modes": ["oauth", "api_key", "mcp"],
                 "runtime_transports": ["direct_api", "mcp"]},
    "pipedrive": {"name": "Pipedrive", "category": "crm",
                  "setup_modes": ["oauth", "api_key", "mcp"],
                  "runtime_transports": ["direct_api", "mcp"]},
    "zoho_crm": {"name": "Zoho CRM", "category": "crm",
                 "setup_modes": ["oauth", "api_key", "mcp"],
                 "runtime_transports": ["direct_api", "mcp"]},
    "intercom": {"name": "Intercom", "category": "support",
                 "setup_modes": ["oauth", "api_key", "mcp"],
                 "runtime_transports": ["direct_api", "mcp"]},
    "docusign": {"name": "DocuSign", "category": "documents",
                 "setup_modes": ["oauth", "api_key", "mcp"],
                 "runtime_transports": ["direct_api", "mcp"]},
    "onepassword": {"name": "1Password", "category": "security",
                    "setup_modes": ["oauth", "mcp"],
                    "runtime_transports": ["mcp"]},
    "figma": {"name": "Figma", "category": "design",
              "setup_modes": ["oauth", "api_key", "mcp"],
              "runtime_transports": ["direct_api", "mcp"]},
    "sentry": {"name": "Sentry", "category": "observability",
               "setup_modes": ["oauth", "api_key", "mcp"],
               "runtime_transports": ["direct_api", "mcp"]},
    "stripe": {"name": "Stripe", "category": "payments",
               "setup_modes": ["api_key", "mcp"],
               "runtime_transports": ["direct_api", "mcp"]},
    "hostinger": {"name": "Hostinger", "category": "hosting",
                  "setup_modes": ["guided_browser", "api_key", "mcp"],
                  "runtime_transports": ["direct_api", "mcp", "browser"]},
    "custom_mcp": {"name": "Custom MCP server", "category": "extensibility",
                   "setup_modes": ["mcp"],
                   "runtime_transports": ["mcp"]},
}

for _connector_id, _manifest in _CONNECTOR_CATALOG.items():
    _manifest['implementation_status'] = 'live' if _connector_id == 'github' else 'planned'
    _manifest['setup_strategy'] = ['guided_browser', 'oauth', 'api_key', 'mcp'] if _connector_id == 'github' \
        else ['oauth', 'api_key', 'mcp', 'guided_browser']


def connector_catalog() -> dict:
    """Return a copy of Cordia's provider-neutral connector manifest catalog."""
    return deepcopy(_CONNECTOR_CATALOG)


def compile_artifacts(profile: dict, connector_states: dict | None = None) -> dict:
    """Return canonical source and runtime Markdown artifacts for one profile.

    ``connector_states`` is an explicit user-confirmed map of catalog id to
    ``confirmed`` or ``suggested``. Unknown ids and unrecognized states are
    ignored rather than invented from a transcript.
    """
    profile = profile or {}
    connector_states = connector_states or profile.get("connector_states") or {}
    connectors = _known_connectors(connector_states)
    return {
        "source/operator.md": _operator(profile),
        "source/connectors.md": _connectors(connectors),
        "source/intent-misses.md": _intent_misses(profile),
        "runtime/fde-tasks.md": _mission(profile, connectors),
        "runtime/permissions.md": _permissions(profile),
        "runtime/workspace-plan.md": _workspace_plan(profile, connectors),
    }


def normalize_connector_states(states: dict | None) -> dict:
    """Keep only catalog connectors carrying an explicit valid user state."""
    return {cid: state for cid, state in (states or {}).items()
            if cid in _CONNECTOR_CATALOG and state in {"confirmed", "suggested"}}


def merge_connector_states(current: dict | None, update: dict | None) -> dict:
    """Apply an explicit connector update without dropping existing choices."""
    merged = normalize_connector_states(current)
    merged.update(normalize_connector_states(update))
    return merged


def assessment_view(profile: dict, connector_states: dict | None = None) -> dict:
    """Return safe, non-scored assessment data for the existing profile surface."""
    profile = profile or {}
    signals = profile.get("signals") or {}
    connectors = _known_connectors(connector_states or profile.get("connector_states"))
    understanding = []
    if signals.get("domain"):
        understanding.append({"label": "Domain and work focus", "value": signals["domain"]})
    if signals.get("primary_goal"):
        understanding.append({"label": "Current goal", "value": signals["primary_goal"]})
    if signals.get("delegation_style"):
        understanding.append({"label": "Human checkpoint preference",
                              "value": signals["delegation_style"].replace("_", " ")})
    return {
        "title": "What Cordia currently understands",
        "understanding": understanding,
        "evidence": [{"summary": item.get("summary", ""),
                      "confidence": item.get("confidence", "emerging")}
                     for item in (profile.get("evidence") or [])[:6]
                     if item.get("summary")],
        "connectors": [{"id": cid, "name": manifest["name"],
                        "status": "Confirmed by user" if state == "confirmed"
                        else "Suggested - not connected",
                        "implementation_status": manifest['implementation_status']}
                       for cid, manifest, state in connectors],
    }


def _known_connectors(states: dict) -> list[tuple[str, dict, str]]:
    return [(cid, _CONNECTOR_CATALOG[cid], state)
            for cid, state in sorted(normalize_connector_states(states).items())]


def _operator(profile: dict) -> str:
    signals = profile.get("signals") or {}
    evidence = profile.get("evidence") or []
    lines = ["# Operator", "", "## What Cordia currently understands"]
    if signals.get("domain"):
        lines.append(f"- Work domain: {signals['domain']}")
    if signals.get("primary_goal"):
        lines.append(f"- Current goal: {signals['primary_goal']}")
    if not signals:
        lines.append("- Surveyor is still learning the operator's work context.")
    lines.extend(["", "## Evidence"])
    if evidence:
        for item in evidence[:8]:
            confidence = item.get("confidence", "emerging")
            lines.append(f"- ({confidence}) {item.get('summary', '').strip()}")
    else:
        lines.append("- No evidence has been collected yet.")
    return "\n".join(lines) + "\n"


def _connectors(connectors: list[tuple[str, dict, str]]) -> str:
    lines = ["# Connectors", "", "Connector records are provider-neutral: Cordia can use a direct API, MCP server, or local bridge when a provider supports it.", "Credentials are not stored in this artifact.", ""]
    if not connectors:
        lines.append("No systems have been confirmed yet. Surveyor should ask which tools the operator wants to connect.")
    for _, manifest, state in connectors:
        label = "Confirmed by user" if state == "confirmed" else "Suggested - not connected"
        lines.extend([f"## {manifest['name']}", f"- Status: {label}",
                      f"- Implementation: {manifest['implementation_status']}",
                      f"- Setup: {', '.join(manifest['setup_modes'])}",
                      f"- Runtime: {', '.join(manifest['runtime_transports'])}", ""])
    return "\n".join(lines).rstrip() + "\n"


def _intent_misses(profile: dict) -> str:
    misses = profile.get("intent_misses") or []
    lines = ["# Intent Misses", "", "This appendable memory records corrections that should change future Cordia behavior.", ""]
    if not misses:
        lines.append("No intent misses recorded yet.")
    for miss in misses:
        lines.extend([f"## Intent Miss: {miss.get('date', 'undated')}",
                      f"Category: {miss.get('category', 'uncategorized')}",
                      f"User correction: {miss.get('correction', '')}",
                      f"Effect on FDE tasks: {miss.get('effect', '')}", ""])
    return "\n".join(lines).rstrip() + "\n"


def _mission(profile: dict, connectors) -> str:
    freeform = profile.get("freeform") or {}
    signals = profile.get("signals") or {}
    lines = ["# FDE Mission Brief", "", "## Current mission"]
    goal = freeform.get("automate") or signals.get("primary_goal")
    lines.append(f"- {goal}" if goal else "- Continue Surveyor conversation to identify the first useful workflow.")
    lines.extend(["", "## Operating guidance", "- Produce evidence-backed drafts and preserve a human checkpoint before consequential external actions."])
    latest_miss = (profile.get('intent_misses') or [])[-1:]
    if latest_miss and latest_miss[0].get('effect'):
        lines.append("- Latest correction: " + str(latest_miss[0]['effect']).strip())
    confirmed = [m["name"] for _, m, state in connectors if state == "confirmed"]
    if confirmed:
        lines.append("- Use confirmed systems when needed: " + ", ".join(confirmed) + ".")
    return "\n".join(lines) + "\n"


def _permissions(profile: dict) -> str:
    signals = profile.get("signals") or {}
    checkpoint = signals.get("delegation_style") != "agent_autonomous" or signals.get("risk_awareness") == "high"
    review = "before any client-facing or irreversible output" if checkpoint else "before external or irreversible actions"
    return "\n".join(["# Permissions", "", "## ALLOW", "- Read confirmed connector data and prepare drafts in the workspace.", "", "## ASK", f"- Pause for approval {review}.", "- Send messages, publish changes, create external records, or run consequential automations.", "", "## DENY", "- Read or reveal passwords, raw API keys, payment credentials, or authentication tokens.", "- Delete external data or perform financial transactions without an explicit future permission grant.", ""])


def _workspace_plan(profile: dict, connectors) -> str:
    freeform = profile.get("freeform") or {}
    screen = freeform.get("screen") or "A focused chat and work surface that can evolve with the operator."
    confirmed = [m["name"] for _, m, state in connectors if state == "confirmed"]
    lines = ["# Workspace Plan", "", "## Proposed surface", f"- {screen}", "", "## Initial windows", "- Cordia Agent conversation", "- Mission and evidence inspection", "- Draft work surface", "", "## Connector state"]
    lines.append("- Confirmed: " + ", ".join(confirmed) if confirmed else "- No connector is connected yet.")
    return "\n".join(lines) + "\n"
