"""Fail-closed storage for repository-local production-review artifacts."""

import json
import os
from pathlib import Path
import tempfile


ARTIFACT_DIRECTORY_NAME = ".production-review"
LEGACY_TEMP_SUFFIX = ".tmp"


def _repository_root(repo_root: Path) -> Path:
    root = Path(repo_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository root is unavailable")
    return root


def _relative_parts(relative_name: str) -> tuple[str, ...]:
    if not isinstance(relative_name, str) or not relative_name:
        raise ValueError("artifact name is invalid")
    relative = Path(relative_name)
    if relative.is_absolute() or relative.anchor or relative.drive:
        raise ValueError("artifact name must be repository-relative")
    parts = relative.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("artifact name is invalid")
    return parts


def _contained(root: Path, path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def artifact_directory(repo_root: Path, *, create: bool = False) -> Path:
    root = _repository_root(repo_root)
    directory = root / ARTIFACT_DIRECTORY_NAME
    if directory.is_symlink():
        raise ValueError("review artifact directory is unsafe")
    if directory.exists() and not directory.is_dir():
        raise ValueError("review artifact directory is unsafe")
    if not _contained(root, directory):
        raise ValueError("review artifact directory is outside the repository")
    if create and not directory.exists():
        directory.mkdir()
        if directory.is_symlink() or not directory.is_dir() or not _contained(root, directory):
            raise ValueError("review artifact directory is unsafe")
    return directory


def artifact_path(
    repo_root: Path,
    relative_name: str,
    *,
    create_parents: bool = False,
) -> Path:
    root = _repository_root(repo_root)
    directory = artifact_directory(root, create=create_parents)
    current = directory
    parts = _relative_parts(relative_name)
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("review artifact parent is unsafe")
        if current.exists() and not current.is_dir():
            raise ValueError("review artifact parent is unsafe")
        if create_parents and not current.exists():
            current.mkdir()
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise ValueError("review artifact parent is unsafe")
        if not _contained(root, current):
            raise ValueError("review artifact parent is outside the repository")

    path = current / parts[-1]
    # Check the lexical path for a link before resolving it. Resolving first would
    # erase the evidence that a repository artifact was redirected elsewhere.
    if path.is_symlink():
        raise ValueError("review artifact path is unsafe")
    if path.exists() and not path.is_file():
        raise ValueError("review artifact path is unsafe")
    if not _contained(root, path):
        raise ValueError("review artifact path is outside the repository")
    return path


def read_text(repo_root: Path, relative_name: str) -> str:
    path = artifact_path(repo_root, relative_name)
    return path.read_text(encoding="utf-8")


def remove_artifacts(repo_root: Path, relative_names: tuple[str, ...]) -> None:
    """Remove only preflighted regular artifact paths, attempting every safe path."""
    directory = artifact_directory(repo_root)
    if not directory.exists():
        return
    candidates = []
    for relative_name in relative_names:
        target = artifact_path(repo_root, relative_name)
        candidates.append(target)
        candidates.append(artifact_path(repo_root, relative_name + LEGACY_TEMP_SUFFIX))
        if target.parent.exists():
            unique_prefix = f".{target.name}-"
            for entry in target.parent.iterdir():
                if entry.name.startswith(unique_prefix) and entry.name.endswith(".tmp"):
                    relative_temp = entry.relative_to(directory).as_posix()
                    candidates.append(artifact_path(repo_root, relative_temp))

    candidates = list(dict.fromkeys(candidates))

    first_error = None
    for candidate in candidates:
        try:
            candidate.unlink(missing_ok=True)
        except OSError as error:
            if first_error is None:
                first_error = error
    if first_error is not None:
        raise first_error


def _atomic_write(repo_root: Path, relative_name: str, data: bytes) -> None:
    root = _repository_root(repo_root)
    target = artifact_path(root, relative_name, create_parents=True)
    # A predictable temp from an older implementation must never be followed.
    artifact_path(root, relative_name + LEGACY_TEMP_SUFFIX)

    descriptor = None
    temporary_path = None
    safe_temporary_path = False
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}-",
            suffix=".tmp",
            dir=str(target.parent),
        )
        temporary_path = Path(temporary_name)
        if temporary_path.parent != target.parent:
            raise ValueError("review temporary artifact is outside its target directory")
        if temporary_path.is_symlink() or not _contained(root, temporary_path):
            raise ValueError("review temporary artifact is unsafe")
        safe_temporary_path = True

        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(data)
            handle.flush()

        artifact_path(root, relative_name)
        if temporary_path.is_symlink() or not _contained(root, temporary_path):
            raise ValueError("review temporary artifact is unsafe")
        temporary_path.replace(target)
        safe_temporary_path = False
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if (
            safe_temporary_path
            and temporary_path is not None
            and temporary_path.exists()
            and not temporary_path.is_symlink()
            and _contained(root, temporary_path)
        ):
            temporary_path.unlink()


def write_bytes_atomically(repo_root: Path, relative_name: str, value: bytes) -> None:
    if not isinstance(value, bytes):
        raise TypeError("artifact bytes are invalid")
    _atomic_write(repo_root, relative_name, value)


def write_text_atomically(repo_root: Path, relative_name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("artifact text is invalid")
    _atomic_write(repo_root, relative_name, value.encode("utf-8"))


def write_json_atomically(repo_root: Path, relative_name: str, value: dict) -> None:
    serialized = json.dumps(value, separators=(",", ":"), ensure_ascii=True) + "\n"
    write_text_atomically(repo_root, relative_name, serialized)
