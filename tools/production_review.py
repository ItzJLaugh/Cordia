from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import time

try:
    from tools.production_review_artifacts import (
        artifact_path,
        remove_artifacts,
        write_json_atomically,
    )
except ModuleNotFoundError:  # Support direct execution from the tools directory.
    from production_review_artifacts import (
        artifact_path,
        remove_artifacts,
        write_json_atomically,
    )


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    cwd: str
    argv: tuple[str, ...]
    timeout_seconds: int


SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
LOG_CAP_BYTES = 2 * 1024 * 1024
SHA_TIMEOUT_SECONDS = 60


def check_specs(platform=None, python=None) -> tuple[CheckSpec, ...]:
    command_platform = os.name if platform is None else platform
    python_command = sys.executable if python is None else python
    npm_command = "npm.cmd" if command_platform == "nt" else "npm"

    return (
        CheckSpec(
            "backend-tests",
            "backend",
            (python_command, "-m", "unittest", "discover", "-s", "tests", "-v"),
            600,
        ),
        CheckSpec("dashboard-install", "dashboard-app", (npm_command, "ci"), 600),
        CheckSpec("dashboard-tests", "dashboard-app", (npm_command, "test"), 300),
        CheckSpec("dashboard-build", "dashboard-app", (npm_command, "run", "build"), 300),
        CheckSpec("desktop-install", "desktop", (npm_command, "ci"), 600),
        CheckSpec("desktop-tests", "desktop", (npm_command, "test"), 300),
        CheckSpec(
            "dashboard-release",
            "desktop",
            (npm_command, "run", "verify:dashboard-release"),
            300,
        ),
        CheckSpec("commit-diff-check", ".", ("git", "diff", "--check", "HEAD^", "HEAD"), 60),
    )


def _validate_expected_sha(expected_sha: str) -> None:
    if not isinstance(expected_sha, str) or SHA_PATTERN.fullmatch(expected_sha) is None:
        raise ValueError("expected SHA must be a lowercase 40-hex SHA")


def _output_bytes(*values) -> bytes:
    chunks = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, bytes):
            chunks.append(value)
        else:
            chunks.append(str(value).encode("utf-8", errors="replace"))
    return b"".join(chunks)


def _write_private_log(repo_root: Path, check_id: str, *output) -> None:
    data = _output_bytes(*output)[:LOG_CAP_BYTES]
    artifact_path(repo_root, f"logs/{check_id}.log", create_parents=True).write_bytes(data)


def _timestamp(now) -> str:
    if isinstance(now, str):
        return now
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime or an ISO timestamp string")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _execute(executor, argv: tuple[str, ...], *, cwd: Path, timeout_seconds: int):
    return executor(
        list(argv),
        cwd=str(cwd),
        shell=False,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout_seconds,
    )


def run_review(repo_root, *, expected_sha, executor, now, platform=None, python=None) -> dict:
    """Run the fixed production checks and return their safe, bounded summary."""
    _validate_expected_sha(expected_sha)
    root = Path(repo_root)
    head = _execute(
        executor,
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        timeout_seconds=SHA_TIMEOUT_SECONDS,
    )
    if head.returncode != 0:
        raise RuntimeError("could not determine checked-out commit")
    if str(head.stdout).strip() != expected_sha:
        raise ValueError("checked-out commit does not match expected SHA")

    checks = []
    for spec in check_specs(platform=platform, python=python):
        started = time.monotonic()
        try:
            completed = _execute(
                executor,
                spec.argv,
                cwd=root / spec.cwd,
                timeout_seconds=spec.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            duration_ms = round((time.monotonic() - started) * 1000)
            _write_private_log(root, spec.check_id, error.output, error.stderr)
            checks.append(
                {
                    "id": spec.check_id,
                    "status": "timed_out",
                    "duration_ms": duration_ms,
                    "diagnostic": "Timed out",
                }
            )
            continue

        duration_ms = round((time.monotonic() - started) * 1000)
        _write_private_log(root, spec.check_id, completed.stdout, completed.stderr)
        if completed.returncode == 0:
            status = "passed"
            diagnostic = "Passed"
        else:
            status = "failed"
            diagnostic = f"Exited with code {completed.returncode}"
        checks.append(
            {
                "id": spec.check_id,
                "status": status,
                "duration_ms": duration_ms,
                "diagnostic": diagnostic,
            }
        )

    return {"commit": expected_sha, "reviewed_at": _timestamp(now), "checks": checks}


def main(argv=None, *, repo_root=None, environ=None, executor=subprocess.run, now=None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments != ["run"]:
        return 2
    environment = os.environ if environ is None else environ
    expected_sha = environment.get("EXPECTED_SHA")
    root = Path.cwd() if repo_root is None else Path(repo_root)
    timestamp = datetime.now(timezone.utc) if now is None else now
    try:
        remove_artifacts(root, ("deterministic.json",))
        result = run_review(
            root,
            expected_sha=expected_sha,
            executor=executor,
            now=timestamp,
        )
        write_json_atomically(root, "deterministic.json", result)
    except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
