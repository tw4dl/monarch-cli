"""MCP server commands for Monarch CLI."""

from __future__ import annotations

import importlib.metadata
from enum import Enum
from typing import Annotated

import typer

from ..core.error_handler import handle_errors
from ..core.exceptions import APIError
from ..output import output

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


class Transport(str, Enum):
    STDIO = "stdio"
    HTTP = "streamable-http"
    SSE = "sse"


def _load_mcp_server() -> object:
    try:
        from monarch_cli.mcp_server import build_mcp_server  # noqa: PLC0415
    except ModuleNotFoundError as e:
        if e.name and e.name.startswith("mcp"):
            raise APIError(
                "MCP support is not installed. Install monarch-cli with its mcp extra.",
                details={"fix": "uv tool install --reinstall 'monarch-cli[mcp]'"},
            ) from None
        raise

    return build_mcp_server()


@app.command("status")
@handle_errors
def status_cmd() -> None:
    """Show MCP server status (dependency + constructability)."""
    try:
        mcp_version = importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        raise APIError(
            "MCP support is not installed. Install monarch-cli with its mcp extra.",
            details={"fix": "uv tool install --reinstall 'monarch-cli[mcp]'"},
        ) from None

    server = _load_mcp_server()
    output(
        {
            "status": "ready",
            "version": mcp_version,
            "tools": _TOOL_NAMES,
            "help": ["monarch mcp start"],
        }
    )

    # Quiet mypy about `server` being unused in runtime paths
    _ = server


@app.command("start")
@handle_errors
def start(
    transport: Annotated[
        Transport,
        typer.Option(
            "--transport",
            help="Transport to use (stdio, streamable-http, sse). Default: stdio.",
        ),
    ] = Transport.STDIO,
) -> None:
    """Start the Monarch MCP server.

    Examples:
        monarch mcp start
        monarch mcp start --transport streamable-http
    """
    server = _load_mcp_server()

    # FastMCP has a `.run(transport=...)` method; keep this command minimal.
    server.run(transport=transport.value)  # type: ignore[attr-defined]
