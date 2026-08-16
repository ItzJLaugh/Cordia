from html import escape
import json
import os
from pathlib import Path
import re
import sys


FINDING_KEYS = {"severity", "title", "evidence", "file", "line", "recommendation"}
AI_KEYS = {"summary", "findings"}
SEVERITIES = {"Critical", "Important", "Minor"}
DETERMINISTIC_CHECK_IDS = {
    "backend-tests",
    "dashboard-install",
    "dashboard-tests",
    "dashboard-build",
    "desktop-install",
    "desktop-tests",
    "dashboard-release",
    "commit-diff-check",
}
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
    r"\b(?:mailto|tel|data|javascript|vbscript):\S+)",
    re.IGNORECASE,
)
HOST_FORM_PATTERN = re.compile(
    r"\b(?![A-Za-z0-9_.-]+\.(?:d\.ts|py|js|jsx|ts|tsx|json|md|yaml|yml|toml|txt|"
    r"html|css|scss|sql|sh|bat|ps1)\b)(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}\b(?:/[^\s]*)?",
    re.IGNORECASE,
)
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
RUN_ID_PATTERN = re.compile(r"[1-9][0-9]{0,19}")
FAILED_DIAGNOSTIC_PATTERN = re.compile(r"Exited with code -?[0-9]{1,10}")
REPOSITORY_URL = "https://github.com/ItzJLaugh/Cordia"
PUBLIC_ARTIFACT_NAMES = ("final.json", "slack.json", "review.md")
MAX_FINDING_LINE = 2_147_483_647
MAX_CHECK_DURATION_MS = 3_600_000
SLACK_SECTION_LIMIT = 3000
SLACK_CONTEXT_LIMIT = 2000


def _is_safe_text(value, *, limit):
    return (
        isinstance(value, str)
        and 0 < len(value) <= limit
        and TOKEN_PATTERN.search(value) is None
        and LOCAL_PATH_PATTERN.search(value) is None
        and POSIX_ABSOLUTE_PATH_PATTERN.search(value) is None
        and URL_PATTERN.search(value) is None
        and HOST_FORM_PATTERN.search(value) is None
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
        if finding["line"] < 1 or finding["line"] > MAX_FINDING_LINE:
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
    if (
        not isinstance(value["checks"], list)
        or not value["checks"]
        or len(value["checks"]) > len(DETERMINISTIC_CHECK_IDS)
    ):
        raise ValueError("deterministic result has invalid checks")

    safe_checks = []
    observed_ids = set()
    for check in value["checks"]:
        if not isinstance(check, dict) or set(check) != {"id", "status", "duration_ms", "diagnostic"}:
            raise ValueError("deterministic result has an invalid check")
        if check["id"] not in DETERMINISTIC_CHECK_IDS or check["id"] in observed_ids:
            raise ValueError("deterministic result has an invalid check")
        observed_ids.add(check["id"])
        if check["status"] not in {"passed", "failed", "timed_out"}:
            raise ValueError("deterministic result has an invalid check status")
        if (
            isinstance(check["duration_ms"], bool)
            or not isinstance(check["duration_ms"], int)
            or not 0 <= check["duration_ms"] <= MAX_CHECK_DURATION_MS
        ):
            raise ValueError("deterministic result has an invalid check duration")
        valid_diagnostic = (
            (check["status"] == "passed" and check["diagnostic"] == "Passed")
            or (check["status"] == "timed_out" and check["diagnostic"] == "Timed out")
            or (
                check["status"] == "failed"
                and isinstance(check["diagnostic"], str)
                and FAILED_DIAGNOSTIC_PATTERN.fullmatch(check["diagnostic"]) is not None
            )
        )
        if not valid_diagnostic:
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


def _section_block(text):
    if len(text) > SLACK_SECTION_LIMIT:
        raise ValueError("Slack section exceeds the bounded text limit")
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _context_block(text):
    if len(text) > SLACK_CONTEXT_LIMIT:
        raise ValueError("Slack context exceeds the bounded text limit")
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text}]}


def _slack_payload(final, *, run_id):
    commit = final["commit"]
    run_url = f"{REPOSITORY_URL}/actions/runs/{run_id}"
    commit_url = f"{REPOSITORY_URL}/commit/{commit}"
    playbook_url = f"{REPOSITORY_URL}/blob/{commit}/docs/PRODUCTION_REVIEW_PLAYBOOK.md"
    failed_checks = sum(check["status"] != "passed" for check in final["checks"])
    status_text = f"*{final['state']}*\nCommit `{commit}` · {len(final['checks'])} checks"
    if failed_checks:
        status_text += f" · {failed_checks} failed or timed out"
    blocks = [_section_block(status_text)]
    check_lines = "\n".join(
        f"• `{check['id']}`: {check['status']}" for check in final["checks"]
    )
    blocks.append(_section_block(f"*Deterministic checks*\n{check_lines}"))
    if final["ai"] is not None:
        summary = _slack_text(final["ai"]["summary"])
        titles = "\n".join(
            f"• *{finding['severity']}*: {_slack_text(finding['title'])} "
            f"— `{_slack_text(finding['file'])}:{finding['line']}`"
            for finding in final["ai"]["findings"]
        )
        review_text = f"*AI advisory summary*\n{summary}"
        if titles:
            review_text += f"\n{titles}"
        blocks.append(_section_block(review_text))
    else:
        blocks.append(
            _section_block("*AI advisory result*\nUnavailable for this review.")
        )
    blocks.append(
        _context_block("Advisory only. A human must validate findings before any change.")
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
        lines.extend(["", "## AI advisory findings", "", _slack_text(final["ai"]["summary"])])
        for finding in final["ai"]["findings"]:
            lines.append(
                f"- **{finding['severity']}** `{finding['file']}:{finding['line']}`: "
                f"{_slack_text(finding['title'])} — {_slack_text(finding['recommendation'])}"
            )
    else:
        lines.extend(["", "## AI advisory findings", "", "Unavailable for this review."])
    return "\n".join(lines) + "\n"


def assemble_review(deterministic, ai_result, *, model_configured, run_id) -> tuple[dict, dict, str]:
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
        "setup_required": not bool(model_configured),
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


def _remove_public_artifacts(artifact_dir: Path) -> None:
    first_error = None
    for name in PUBLIC_ARTIFACT_NAMES:
        path = artifact_dir / name
        for candidate in (path, path.with_name(path.name + ".tmp")):
            try:
                candidate.unlink(missing_ok=True)
            except OSError as error:
                if first_error is None:
                    first_error = error
    if first_error is not None:
        raise first_error


def _load_ai_review(root: Path, configured_path: str | None) -> dict | None:
    """Load only a repository-local bounded model file, never raw model output."""
    if not isinstance(configured_path, str) or not configured_path:
        return None
    candidate = Path(configured_path)
    if candidate.is_absolute():
        return None
    try:
        path = (root / candidate).resolve(strict=False)
        path.relative_to(root.resolve())
        if path.is_symlink():
            return None
        return validate_ai_result(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None


def main(argv=None, *, repo_root=None, environ=None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments != ["assemble"]:
        return 2
    environment = os.environ if environ is None else environ
    root = Path.cwd() if repo_root is None else Path(repo_root)
    artifact_dir = root / ".production-review"
    try:
        _remove_public_artifacts(artifact_dir)
        with (artifact_dir / "deterministic.json").open("r", encoding="utf-8") as handle:
            deterministic = json.load(handle)
        ai_result = _load_ai_review(root, environment.get("AI_REVIEW_PATH"))
        final, slack, markdown = assemble_review(
            deterministic,
            ai_result,
            model_configured=environment.get("MODEL_REVIEW_CONFIGURED") == "true",
            run_id=environment.get("GITHUB_RUN_ID"),
        )
        _write_json_atomically(artifact_dir / "final.json", final)
        _write_json_atomically(artifact_dir / "slack.json", slack)
        _write_text_atomically(artifact_dir / "review.md", markdown)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        try:
            _remove_public_artifacts(artifact_dir)
        except OSError:
            pass
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
