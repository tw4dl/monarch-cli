"""MCP server commands for Monarch CLI."""

from __future__ import annotations

import importlib.metadata
from typing import Annotated

import typer

from ..core.error_handler import handle_errors
from ..output import console

app = typer.Typer(
    help="Run the Monarch MCP server",
    no_args_is_help=True,
)


@app.callback()
def _mcp_callback() -> None:
    """MCP server commands."""


_TOOL_NAMES: list[str] = [
    "monarch.run",
    "monarch.auth_login",
]


def _load_mcp_server() -> object:
    try:
        from monarch_cli.mcp_server import build_mcp_server  # noqa: PLC0415
    except ModuleNotFoundError as e:
        if e.name and e.name.startswith("mcp"):
            console.print("[red]✗ MCP dependency not installed.[/red]")
            console.print("Install with: [cyan]uv sync --extra mcp[/cyan]")
            raise typer.Exit(1) from None
        raise

    return build_mcp_server()


@app.command("status")
@handle_errors
def status_cmd() -> None:
    """Show MCP server status (dependency + constructability)."""
    try:
        mcp_version = importlib.metadata.version("mcp")
        console.print(f"[green]✓[/green] MCP dependency installed ([dim]{mcp_version}[/dim])")
    except importlib.metadata.PackageNotFoundError:
        console.print("[red]✗ MCP dependency not installed.[/red]")
        console.print("Install with: [cyan]uv sync --extra mcp[/cyan]")
        raise typer.Exit(1) from None

    server = _load_mcp_server()
    console.print("[green]✓[/green] MCP server constructable")
    console.print("[bold]Tools:[/bold] " + ", ".join(f"[cyan]{n}[/cyan]" for n in _TOOL_NAMES))
    console.print()
    console.print("Start with: [cyan]monarch mcp start[/cyan]")

    # Quiet mypy about `server` being unused in runtime paths
    _ = server


@app.command("start")
@handle_errors
def start(
    transport: Annotated[
        str,
        typer.Option(
            "--transport",
            help="Transport to use (stdio, streamable-http, sse). Default: stdio.",
        ),
    ] = "stdio",
) -> None:
    """Start the Monarch MCP server.

    Examples:
        monarch mcp start
        monarch mcp start --transport streamable-http
    """
    server = _load_mcp_server()

    # FastMCP has a `.run(transport=...)` method; keep this command minimal.
    server.run(transport=transport)  # type: ignore[attr-defined]
