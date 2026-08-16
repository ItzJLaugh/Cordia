from html import escape
import json
import os
from pathlib import Path
import re
import sys


FINDING_KEYS = {"severity", "title", "evidence", "file", "line", "recommendation"}
AI_KEYS = {"summary", "findings"}
SEVERITIES = {"Critical", "Important", "Minor"}
PATH_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")
TOKEN_PATTERN = re.compile(
    r"(?:github_pat_|gh[pousr]_|sk-ant-|xox[baprs]-|xapp-)", re.IGNORECASE
)
LOCAL_PATH_PATTERN = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\)",
    re.IGNORECASE,
)
POSIX_ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9])/(?=$|[^\s])")
URL_PATTERN = re.compile(
    r"(?:\b[A-Za-z][A-Za-z0-9+.-]*:/{1,2}|"
    r"\b(?:mailto|tel|data|javascript|vbscript):\S+|"
    r"\bwww\.[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b)",
    re.IGNORECASE,
)
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
RUN_ID_PATTERN = re.compile(r"[1-9][0-9]{0,19}")
REPOSITORY_URL = "https://github.com/ItzJLaugh/Cordia"


def _is_safe_text(value, *, limit):
    return (
        isinstance(value, str)
        and 0 < len(value) <= limit
        and TOKEN_PATTERN.search(value) is None
        and LOCAL_PATH_PATTERN.search(value) is None
        and POSIX_ABSOLUTE_PATH_PATTERN.search(value) is None
        and URL_PATTERN.search(value) is None
    )


def _is_safe_repository_path(value):
    return (
        _is_safe_text(value, limit=200)
        and PATH_PATTERN.fullmatch(value) is not None
        and ".." not in value.split("/")
    )


def validate_ai_result(value: str | None) -> dict | None:
    """Return the exact bounded AI model, or reject the complete value."""
    if not isinstance(value, str):
        return None
    try:
        result = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(result, dict) or set(result) != AI_KEYS:
        return None
    if not _is_safe_text(result["summary"], limit=600):
        return None
    findings = result["findings"]
    if not isinstance(findings, list) or len(findings) > 5:
        return None

    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != FINDING_KEYS:
            return None
        if finding["severity"] not in SEVERITIES:
            return None
        if not _is_safe_text(finding["title"], limit=120):
            return None
        if not _is_safe_text(finding["evidence"], limit=300):
            return None
        if not _is_safe_repository_path(finding["file"]):
            return None
        if isinstance(finding["line"], bool) or not isinstance(finding["line"], int):
            return None
        if finding["line"] < 1:
            return None
        if not _is_safe_text(finding["recommendation"], limit=300):
            return None
    return result


def _validated_ai_object(value):
    if not isinstance(value, dict):
        return None
    try:
        return validate_ai_result(json.dumps(value, ensure_ascii=True))
    except (TypeError, ValueError):
        return None


def _safe_deterministic_result(value):
    if not isinstance(value, dict) or set(value) != {"commit", "reviewed_at", "checks"}:
        raise ValueError("deterministic result has an invalid shape")
    if not isinstance(value["commit"], str) or COMMIT_PATTERN.fullmatch(value["commit"]) is None:
        raise ValueError("deterministic result has an invalid commit")
    if not isinstance(value["reviewed_at"], str) or not value["reviewed_at"]:
        raise ValueError("deterministic result has an invalid timestamp")
    if not isinstance(value["checks"], list) or not value["checks"]:
        raise ValueError("deterministic result has invalid checks")

    safe_checks = []
    for check in value["checks"]:
        if not isinstance(check, dict) or set(check) != {"id", "status", "duration_ms", "diagnostic"}:
            raise ValueError("deterministic result has an invalid check")
        if not isinstance(check["id"], str) or not check["id"]:
            raise ValueError("deterministic result has an invalid check")
        if check["status"] not in {"passed", "failed", "timed_out"}:
            raise ValueError("deterministic result has an invalid check status")
        if isinstance(check["duration_ms"], bool) or not isinstance(check["duration_ms"], int):
            raise ValueError("deterministic result has an invalid check duration")
        if not isinstance(check["diagnostic"], str) or not check["diagnostic"]:
            raise ValueError("deterministic result has an invalid check diagnostic")
        safe_checks.append(dict(check))
    return {
        "commit": value["commit"],
        "reviewed_at": value["reviewed_at"],
        "checks": safe_checks,
    }


def _review_state(checks, ai_result):
    if any(check["status"] != "passed" for check in checks):
        return "CHECKS FAILED"
    return "REVIEW READY" if ai_result is not None else "REVIEW UNAVAILABLE"


def _slack_text(value):
    return escape(value, quote=False)


def _slack_payload(final, *, run_id):
    commit = final["commit"]
    run_url = f"{REPOSITORY_URL}/actions/runs/{run_id}"
    commit_url = f"{REPOSITORY_URL}/commit/{commit}"
    playbook_url = f"{REPOSITORY_URL}/blob/{commit}/docs/PRODUCTION_REVIEW_PLAYBOOK.md"
    failed_checks = sum(check["status"] != "passed" for check in final["checks"])
    status_text = f"*{final['state']}*\nCommit `{commit}` · {len(final['checks'])} checks"
    if failed_checks:
        status_text += f" · {failed_checks} failed or timed out"
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": status_text}}]
    if final["ai"] is not None:
        summary = _slack_text(final["ai"]["summary"])
        titles = "\n".join(
            f"• *{finding['severity']}*: {_slack_text(finding['title'])}"
            for finding in final["ai"]["findings"]
        )
        review_text = f"*Claude advisory summary*\n{summary}"
        if titles:
            review_text += f"\n{titles}"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": review_text}})
    else:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Claude advisory result*\nUnavailable for this review.",
                },
            }
        )
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Advisory only. A human must validate findings before any change.",
                }
            ],
        }
    )
    buttons = [
        ("Open full review", run_url),
        ("View commit", commit_url),
        ("Human review guide", playbook_url),
    ]
    if failed_checks:
        buttons.append(("View failed checks", run_url))
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": label}, "url": url}
                for label, url in buttons
            ],
        }
    )
    return {"blocks": blocks}


def _review_markdown(final, *, run_id):
    lines = [
        "# Cordia daily production review",
        "",
        f"**State:** {final['state']}",
        f"**Commit:** `{final['commit']}`",
        f"**Reviewed at:** {final['reviewed_at']}",
        f"**Full run:** {REPOSITORY_URL}/actions/runs/{run_id}",
        "",
        "## Deterministic checks",
        "",
    ]
    lines.extend(
        f"- {check['id']}: {check['status']} ({check['duration_ms']} ms) — {check['diagnostic']}"
        for check in final["checks"]
    )
    if final["ai"] is not None:
        lines.extend(["", "## Claude advisory findings", "", _slack_text(final["ai"]["summary"])])
        for finding in final["ai"]["findings"]:
            lines.append(
                f"- **{finding['severity']}** `{finding['file']}:{finding['line']}`: "
                f"{_slack_text(finding['title'])} — {_slack_text(finding['recommendation'])}"
            )
    else:
        lines.extend(["", "## Claude advisory findings", "", "Unavailable for this review."])
    return "\n".join(lines) + "\n"


def assemble_review(deterministic, ai_result, *, anthropic_configured, run_id) -> tuple[dict, dict, str]:
    """Combine only bounded models into a fixed-link human review artifact."""
    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError("run ID must be a positive decimal GitHub Actions run ID")
    safe_deterministic = _safe_deterministic_result(deterministic)
    safe_ai_result = _validated_ai_object(ai_result)
    final = {
        "state": _review_state(safe_deterministic["checks"], safe_ai_result),
        "commit": safe_deterministic["commit"],
        "reviewed_at": safe_deterministic["reviewed_at"],
        "checks": safe_deterministic["checks"],
        "setup_required": not bool(anthropic_configured),
        "ai": safe_ai_result,
    }
    return final, _slack_payload(final, run_id=run_id), _review_markdown(final, run_id=run_id)


def _write_json_atomically(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, separators=(",", ":"), ensure_ascii=True)
        handle.write("\n")
    temporary_path.replace(path)


def _write_text_atomically(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    temporary_path.write_text(value, encoding="utf-8", newline="\n")
    temporary_path.replace(path)


def main(argv=None, *, repo_root=None, environ=None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments != ["assemble"]:
        return 2
    environment = os.environ if environ is None else environ
    root = Path.cwd() if repo_root is None else Path(repo_root)
    artifact_dir = root / ".production-review"
    try:
        with (artifact_dir / "deterministic.json").open("r", encoding="utf-8") as handle:
            deterministic = json.load(handle)
        ai_result = validate_ai_result(environment.get("AI_REVIEW_JSON"))
        final, slack, markdown = assemble_review(
            deterministic,
            ai_result,
            anthropic_configured=environment.get("ANTHROPIC_CONFIGURED") == "true",
            run_id=environment.get("GITHUB_RUN_ID"),
        )
        _write_json_atomically(artifact_dir / "final.json", final)
        _write_json_atomically(artifact_dir / "slack.json", slack)
        _write_text_atomically(artifact_dir / "review.md", markdown)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
