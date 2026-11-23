"""Native hook wire endpoint; lifecycle protocols are separate from CLI data output."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from ..core.config import get_config_dir
from ..core.hook_runtime import run_hook
from ..output.toon import encode


def session_hook(
    state_dir: Annotated[Path | None, typer.Option("--state-dir")] = None,
) -> None:
    """Consume a native lifecycle event on stdin; never block the host session."""
    try:
        raw = sys.stdin.read(65537)
        if len(raw) > 65536:
            return
        event = json.loads(raw)
        if not isinstance(event, dict):
            return
        result = run_hook(event, state_dir or get_config_dir())
        if event.get("hook_event_name") == "SessionStart" and result is not None:
            print(encode({"monarch": result}))
        elif event.get("hook_event_name") == "Stop":
            print("{}")  # Codex Stop requires JSON and must never continue the host turn.
    except Exception:
        # Hook input/config/network failures are diagnostics, not blocking decisions.
        print("Monarch session context unavailable; run monarch auth doctor.", file=sys.stderr)
