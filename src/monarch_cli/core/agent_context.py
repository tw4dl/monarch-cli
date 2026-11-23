"""Per-invocation AXI presentation preferences; never persisted into user config."""

from contextvars import ContextVar
from typing import Any

import click

ACTIVE: ContextVar[bool] = ContextVar("monarch_axi_active", default=False)
OPTIONS: ContextVar[dict[str, Any] | None] = ContextVar("monarch_axi_options", default=None)


def options() -> dict[str, Any]:
    return OPTIONS.get() or {}


def command_path() -> str:
    """Return the current command path without the executable name."""
    context = click.get_current_context(silent=True)
    names = []
    while context and context.parent:
        if context.info_name:
            names.append(context.info_name)
        context = context.parent
    return " ".join(reversed(names))
