"""Idempotent native hook registration, preserving unrelated user configuration."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shlex
import stat
import sys
import tempfile
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .config import get_config_dir

MARKER = "_session-hook"


def load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Expected an object in {path.name}")
    return data


def write_if_changed(path: Path, content: str) -> None:
    """Atomically replace only changed files; keep permissions and private defaults."""
    if path.exists() and path.read_text() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".monarch-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


@contextlib.contextmanager
def locked(directory: Path) -> Iterator[None]:
    """Serialize Monarch writers across its invocations on Unix."""
    import fcntl

    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".hooks.lock").open("a") as stream:
        os.fchmod(stream.fileno(), 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _native_config(
    path: Path, executable: list[str], provider: str, state_dir: Path
) -> dict[str, Any]:
    data = load_object(path)
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"Invalid hooks in {path.name}")
    events = ["SessionStart", "Stop" if provider == "codex" else "SessionEnd"]
    for event in events:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"Invalid {event} hooks in {path.name}")
        kept = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError(f"Invalid {event} group in {path.name}")
            others = []
            for handler in group["hooks"]:
                if not isinstance(handler, dict):
                    raise ValueError(f"Invalid {event} handler in {path.name}")
                command = handler.get("command", "")
                try:
                    ours = isinstance(command, str) and MARKER in shlex.split(command)
                except ValueError:
                    ours = False
                if not ours:
                    others.append(handler)
            if others:
                kept.append({**group, "hooks": others})
        command = shlex.join([*executable, MARKER, "--state-dir", str(state_dir.resolve())])
        handler = {
            "type": "command",
            "command": command,
            "timeout": 3 if event != "SessionStart" else 15,
        }
        kept.append({"hooks": [handler]})
        hooks[event] = kept
    return data


def _enable_codex(content: str) -> str:
    data = tomllib.loads(content)
    if data.get("features", {}).get("hooks") is True:
        return content
    # Preserve comments/formatting instead of serializing unrelated settings.
    lines = content.splitlines(keepends=True)
    start = next(
        (i for i, line in enumerate(lines) if re.match(r"\s*\[features\]\s*(?:#.*)?$", line)), None
    )
    if start is None:
        if "features" in data:
            raise ValueError("Cannot safely update the existing features table")
        updated = content.rstrip() + "\n\n[features]\nhooks = true\n"
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")),
            len(lines),
        )
        found = False
        for i in range(start + 1, end):
            if re.match(r"\s*hooks\s*=", lines[i]):
                lines[i] = re.sub(r"(hooks\s*=\s*)(true|false)", r"\g<1>true", lines[i], count=1)
                found = True
                break
        if not found:
            lines.insert(start + 1, "hooks = true\n")
        updated = "".join(lines)
    if tomllib.loads(updated).get("features", {}).get("hooks") is not True:
        raise ValueError("Cannot safely enable native hooks")
    return updated


def install_hooks(
    executable: list[str], *, codex_home: Path, claude_home: Path, state_dir: Path, cwd: Path
) -> None:
    """Prepare and validate all configs before changing any, then repair our entries."""
    if not executable or not Path(executable[0]).is_absolute():
        raise ValueError("Hook executable must use an absolute path")
    with locked(state_dir):
        targets = {
            codex_home / "hooks.json": _native_config(
                codex_home / "hooks.json", executable, "codex", state_dir
            ),
            claude_home / "settings.json": _native_config(
                claude_home / "settings.json", executable, "claude", state_dir
            ),
        }
        config_path = codex_home / "config.toml"
        config = _enable_codex(config_path.read_text() if config_path.exists() else "")
        registry = load_object(state_dir / "hooks.json")
        scopes = registry.setdefault("directories", [])
        if not isinstance(scopes, list) or any(not isinstance(p, str) for p in scopes):
            raise ValueError("Invalid registered hook directories")
        resolved = cwd.resolve()
        # A home/root scope would expose financial context in unrelated projects.
        if resolved not in {Path.home().resolve(), Path(resolved.anchor)}:
            scopes[:] = sorted({*scopes, str(resolved)})
        for path, data in targets.items():
            write_if_changed(path, json.dumps(data, indent=2) + "\n")
        write_if_changed(config_path, config)
        write_if_changed(state_dir / "hooks.json", json.dumps(registry, indent=2) + "\n")


def auto_install() -> None:
    """Use the active console script; module invocation uses an absolute Python path."""
    if os.environ.get("MONARCH_HOOKS_DISABLED", "").lower() in {"1", "true", "yes"}:
        return
    if os.name == "nt":
        return  # Native shell command registration requires platform-specific quoting.
    invoked = Path(sys.argv[0]).absolute()
    executable = (
        [str(invoked)]
        if invoked.name in {"monarch", "monarch-cli"}
        else [sys.executable, "-m", "monarch_cli.main"]
    )
    install_hooks(
        executable,
        codex_home=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))),
        claude_home=Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))),
        state_dir=get_config_dir(),
        cwd=Path.cwd(),
    )
