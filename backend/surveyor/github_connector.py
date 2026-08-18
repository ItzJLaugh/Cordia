"""Read-only GitHub REST adapter. Tokens stay at the execution boundary."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


API_ROOT = "https://api.github.com"
API_VERSION = "2026-03-10"


class ConnectorUnavailable(RuntimeError):
    pass


class AuthorizationRejected(ConnectorUnavailable):
    """The provider reached GitHub, but the submitted credential was rejected."""
    pass


def validate_token(token: str, transport=None) -> dict:
    """Validate a submitted token through the same bounded read Cordia will use.

    The token never leaves this adapter except as the authorization header; the
    returned metadata is intentionally safe to retain in setup/audit responses.
    """
    return list_repositories(token, transport=transport)


def list_repositories(token: str, transport=None) -> dict:
    """Return only fields needed by a Cordia-native repository window."""
    if not (token or "").strip():
        raise ConnectorUnavailable("GitHub is not configured on this Cordia deployment.")
    url = API_ROOT + "/user/repos?per_page=30&sort=updated"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token.strip(),
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "Cordia-FDE",
    }
    try:
        rows = transport(url, headers) if transport else _get_json(url, headers)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthorizationRejected("GitHub authorization was not accepted.") from None
        raise ConnectorUnavailable("GitHub could not be reached right now.") from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise ConnectorUnavailable("GitHub could not be reached right now.") from None
    if not isinstance(rows, list):
        raise ConnectorUnavailable("GitHub returned an unexpected repository response.")
    return {
        "repositories": [_summary(row) for row in rows[:30] if isinstance(row, dict)],
        "repository_limit": 30,
    }


def _get_json(url: str, headers: dict):
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _summary(row: dict) -> dict:
    return {
        "name": str(row.get("full_name") or row.get("name") or "Untitled repository"),
        "private": bool(row.get("private")),
        "description": str(row.get("description") or ""),
        "url": str(row.get("html_url") or ""),
        "default_branch": str(row.get("default_branch") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }
