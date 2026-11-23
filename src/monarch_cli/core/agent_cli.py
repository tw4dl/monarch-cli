"""Shared Click boundary: presentation flags and structured parser failures."""

from __future__ import annotations

import difflib
import json
import sys
from typing import Any

import click
from typer.core import TyperGroup

from .agent_context import ACTIVE, OPTIONS, options

_FORMATS = ["toon", "json", "plain", "table", "csv", "compact"]


def _preference(ctx: click.Context, param: click.Parameter, value: Any) -> None:  # noqa: ARG001
    state = OPTIONS.get()
    if state is not None and value is not None and value is not False:
        key = (param.name or "").removeprefix("axi_")
        if key == "fields" and any(
            not segment.strip() for field in value.split(",") for segment in field.split(".")
        ):
            raise click.BadParameter(
                "Use nonempty comma-separated field paths.", ctx=ctx, param=param
            )
        if key == "json":
            state["format"] = "json"
        else:
            state[key] = value


def _configure(command: click.Command, path: str = "monarch") -> None:
    existing = {flag for p in command.params if isinstance(p, click.Option) for flag in p.opts}
    specifications: list[tuple[str, dict[str, Any]]] = [
        ("--json", {"is_flag": True, "help": "Output the complete JSON schema."}),
        (
            "--fields",
            {"default": None, "help": "Select comma-separated fields (dotted paths supported)."},
        ),
        ("--full", {"is_flag": True, "help": "Show all fields and full text without truncation."}),
        (
            "--format",
            {
                "default": None,
                "type": click.Choice(_FORMATS),
                "help": "Output format (default: toon).",
            },
        ),
    ]
    for flag, kwargs in specifications:
        if flag not in existing:
            command.params.append(
                click.Option(
                    [flag, "axi_" + flag.removeprefix("--")],
                    expose_value=False,
                    callback=_preference,
                    **kwargs,
                )
            )
    if isinstance(command, click.Group):
        for name, child in command.commands.items():
            _configure(child, f"{path} {name}")
    from .help_reference import configure_help

    configure_help(command, path)


def _usage_help(exc: click.ClickException) -> str:
    context = getattr(exc, "ctx", None)
    path = context.command_path if context else "monarch"
    if isinstance(exc, click.MissingParameter):
        from .help_reference import repair_example

        return repair_example(context, exc.param) if context else "monarch auth setup"
    if isinstance(exc, click.BadParameter) and context:
        from .help_reference import repair_example

        return repair_example(context, exc.param)
    if isinstance(exc, click.BadOptionUsage) and context:
        from .help_reference import repair_example

        option = next(
            (
                p
                for p in context.command.params
                if isinstance(p, click.Option) and exc.option_name in p.opts
            ),
            None,
        )
        return repair_example(context, option)
    if isinstance(exc, click.UsageError) and context and isinstance(context.command, click.Group):
        message = exc.format_message()
        unknown = message.split("'")[1] if "'" in message else ""
        matches = difflib.get_close_matches(unknown, context.command.commands, n=1)
        if matches:
            child = context.command.commands[matches[0]]
            action = ""
            if isinstance(child, click.Group):
                action = next(
                    (
                        f" {word}"
                        for word in ("list", "status", "summary")
                        if word in child.commands
                    ),
                    "",
                )
            return f"{path} {matches[0]}{action}"
    if context:
        from .help_reference import repair_example

        return repair_example(context)
    return "monarch auth setup"


def _recover_context(root: click.Command, argv: list[str]) -> click.Context:
    """Recover command identity without evaluating callbacks or opening dependencies."""
    context = click.Context(root, info_name="monarch", resilient_parsing=True)
    cursor = 0
    while cursor < len(argv) and isinstance(context.command, click.Group):
        token = argv[cursor]
        option = next(
            (
                p
                for p in context.command.params
                if isinstance(p, click.Option)
                and token.partition("=")[0] in [*p.opts, *p.secondary_opts]
            ),
            None,
        )
        if option:
            cursor += 1 + (option.nargs if not option.is_flag and "=" not in token else 0)
            continue
        child = context.command.commands.get(token)
        if child is None:
            break
        context = click.Context(child, parent=context, info_name=token, resilient_parsing=True)
        cursor += 1
    return context


def _usage_error(exc: click.ClickException, argv: list[str], root: click.Command) -> None:
    from ..output.toon import encode

    if isinstance(exc, click.UsageError) and exc.ctx is None:
        exc.ctx = _recover_context(root, argv)
    payload = {
        "error": True,
        "code": "INVALID_INPUT",
        "message": exc.format_message(),
        "help": [_usage_help(exc)],
    }
    context = getattr(exc, "ctx", None)
    chosen = (context.params.get("format") if context else None) or options().get("format")
    for argument in argv:
        if argument.startswith("--format="):
            chosen = argument.partition("=")[2]
    if "--format" in argv:
        index = argv.index("--format") + 1
        if index < len(argv):
            chosen = argv[index]
    if "--json" in argv or chosen in {"json", "compact"}:
        print(json.dumps(payload, indent=2))
    else:
        print(encode(payload))


class AgentGroup(TyperGroup):
    """Configure the entire public command tree without modifying command signatures."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        _configure(self)

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        from .help_reference import configure_help

        # Typer adds shell completion parameters after constructing the root group.
        configure_help(self, "monarch")
        super().format_help(ctx, formatter)

    def main(self, *args: Any, **kwargs: Any) -> Any:
        argv = list(kwargs.get("args") or (args[0] if args else sys.argv[1:]))
        active = ACTIVE.set(True)
        preferences = OPTIONS.set({"argv": argv})
        standalone = kwargs.pop("standalone_mode", True)
        try:
            if "_session-hook" not in argv:
                from .hooks import auto_install

                try:
                    auto_install()
                except (OSError, ValueError):
                    print(
                        "Monarch hook registration unavailable; "
                        "check agent configuration permissions and syntax.",
                        file=sys.stderr,
                    )
            try:
                result = super().main(*args, **{**kwargs, "standalone_mode": False})
            except click.ClickException as exc:
                _usage_error(exc, argv, self)
                if standalone:
                    raise SystemExit(2) from None
                return 2
            if standalone:
                raise SystemExit(result if isinstance(result, int) else 0)
            return result
        finally:
            OPTIONS.reset(preferences)
            ACTIVE.reset(active)
