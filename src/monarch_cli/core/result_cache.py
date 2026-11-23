"""Small private, expiring cache for reading full write results without replay."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import get_config_dir
from .exceptions import APIError, NotFoundError, ValidationError

MAX_BYTES = 10 * 1024 * 1024
MAX_ENTRIES = 20
MAX_AGE = 24 * 60 * 60
_ID = re.compile(r"[a-f0-9]{32}")


def _directory() -> Path:
    path = get_config_dir() / "results"
    if path.is_symlink():
        raise APIError("Result cache must be a private directory, not a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def save_result(data: Any) -> str:
    content = json.dumps(data, default=str, ensure_ascii=False).encode()
    if len(content) > MAX_BYTES:
        raise APIError(
            "Full result exceeds the 10 MiB local cache limit; inspect the target instead"
        )
    directory = _directory()
    identity = uuid.uuid4().hex
    target = directory / f"{identity}.json"
    descriptor, temporary = tempfile.mkstemp(prefix=".result-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
        os.replace(temporary, target)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temporary)
    for index, (entry, modified, _) in enumerate(_entries(directory)):
        if index >= MAX_ENTRIES or time.time() - modified > MAX_AGE:
            with suppress(FileNotFoundError):
                entry.unlink()  # Only app-generated cache entries; never user input paths.
    return identity


def _entries(directory: Path) -> list[tuple[Path, float, int]]:
    entries = []
    for path in directory.glob("*.json"):
        with suppress(FileNotFoundError):
            if _ID.fullmatch(path.stem) and not path.is_symlink():
                info = path.stat()
                entries.append((path, info.st_mtime, info.st_size))
    return sorted(entries, key=lambda item: (item[1], item[0].name), reverse=True)


def list_results() -> list[dict[str, Any]]:
    directory = _directory()
    rows = []
    for path, modified, size in _entries(directory):
        if time.time() - modified <= MAX_AGE:
            rows.append(
                {
                    "id": path.stem,
                    "saved_at": datetime.fromtimestamp(modified, UTC).isoformat(),
                    "size_bytes": size,
                }
            )
    return sorted(rows, key=lambda row: row["saved_at"], reverse=True)


def load_result(identity: str) -> Any:
    if not _ID.fullmatch(identity):
        raise ValidationError("Invalid cached result ID", details={"fix": "monarch result list"})
    target = _directory() / f"{identity}.json"
    if (
        target.is_symlink()
        or not target.is_file()
        or time.time() - target.stat().st_mtime > MAX_AGE
    ):
        raise NotFoundError(
            "Cached result missing or expired", details={"fix": "monarch result list"}
        )
    if target.stat().st_size > MAX_BYTES:
        raise APIError("Cached result exceeds the size limit")
    try:
        with target.open() as stream:
            return json.load(stream)
    except (OSError, ValueError) as exc:
        raise APIError("Cannot read cached result", details={"fix": "monarch result list"}) from exc
