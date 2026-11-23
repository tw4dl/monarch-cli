"""Bounded lifecycle context and private session metadata, without financial writes."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .dashboard import dashboard
from .hooks import load_object, locked, write_if_changed


def changed_files(cwd: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-z", "--untracked-files=normal", "--", "."],
            cwd=cwd,
            capture_output=True,
            timeout=1,
            check=True,
        )
        # Rename records contain an additional path. Count each touched path once.
        return sorted(
            {
                entry[3:] if len(entry) > 3 and entry[2:3] == " " else entry
                for entry in result.stdout.decode(errors="replace").split("\0")
                if entry
            }
        )
    except (OSError, subprocess.SubprocessError):
        return []


def _transcript_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        return {}
    size = path.stat().st_size
    # Retain a reference and shape counts, never conversation text or tool arguments.
    with path.open("rb") as stream:
        stream.seek(max(0, size - 262144))
        tail = stream.read(262144)
    calls = 0
    for line in tail.splitlines():
        try:
            record = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(record, dict):
            continue
        payload = record.get("payload", record)
        if isinstance(payload, dict) and payload.get("type") in {
            "function_call",
            "custom_tool_call",
            "tool_use",
        }:
            calls += 1
        message = record.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), list):
            calls += sum(
                isinstance(item, dict) and item.get("type") == "tool_use"
                for item in message["content"]
            )
    return {
        "transcript_path": str(path),
        "transcript_bytes": size,
        "tool_calls": calls,
        "transcript_count_is_tail": size > 262144,
    }


def run_hook(event: dict[str, Any], state_dir: Path) -> dict[str, Any] | None:
    cwd_value = event.get("cwd")
    if not isinstance(cwd_value, str) or not Path(cwd_value).is_absolute():
        return None
    cwd = Path(cwd_value).resolve()
    registry = load_object(state_dir / "hooks.json")
    directories = registry.get("directories", [])
    if not isinstance(directories, list):
        return None
    scopes = [
        Path(p).resolve() for p in directories if isinstance(p, str) and Path(p).is_absolute()
    ]
    matching = [scope for scope in scopes if cwd.is_relative_to(scope)]
    if not matching:
        return None
    scope = max(matching, key=lambda p: len(p.parts))
    event_name = event.get("hook_event_name")
    history_path = state_dir / "hook-history.json"
    if event_name == "SessionStart":
        try:
            data = dashboard()
        except Exception:
            # Keep registered-session failures visible without exposing provider errors
            # or preventing the agent host from starting its session.
            data = {
                "status": "unavailable",
                "message": "Monarch session context could not be loaded.",
                "help": ["monarch auth doctor"],
            }
        previous = load_object(history_path).get(str(scope))
        if isinstance(previous, dict):
            data["previous_session"] = {
                key: previous[key]
                for key in (
                    "ended_at",
                    "working_tree_file_count",
                    "tool_calls",
                    "transcript_count_is_tail",
                )
                if key in previous
            }
        return data
    if event_name in {"SessionEnd", "Stop"}:
        files = changed_files(scope)
        session_id = str(event.get("session_id", ""))
        record = {
            "ended_at": datetime.now(UTC).isoformat(),
            "session_hash": hashlib.sha256(session_id.encode()).hexdigest()[:16],
            "working_tree_files": files[:100],
            "working_tree_file_count": len(files),
            "working_tree_files_truncated": len(files) > 100,
            "event": event_name,
            **_transcript_metadata(event.get("transcript_path")),
        }
        with locked(state_dir):
            history = load_object(history_path)
            history[str(scope)] = record
            # Bound retained metadata to the latest 100 directory scopes.
            history = dict(list(history.items())[-100:])
            write_if_changed(history_path, json.dumps(history, indent=2) + "\n")
    return None
