"""End-to-end stdio MCP integration test."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mcp.client.stdio import StdioServerParameters, stdio_client

from mcp import ClientSession


@pytest.mark.asyncio
async def test_stdio_server_lists_tools_and_runs_version() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server_script = repo_root / "mcp" / "monarch_cli_server.py"

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_script)],
        cwd=str(repo_root),
        env={"MONARCH_MCP_TRANSPORT": "stdio"},
    )

    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()

        tools = await session.list_tools()
        tool_names = {t.name for t in tools.tools}
        assert "monarch.run" in tool_names
        assert "monarch.auth_login" in tool_names

        result = await session.call_tool("monarch.run", {"argv": ["--version"]})
        assert not result.isError
        assert result.structuredContent is not None
        assert result.structuredContent["exit_code"] == 0
        assert "monarch-cli" in result.structuredContent["stdout"]
