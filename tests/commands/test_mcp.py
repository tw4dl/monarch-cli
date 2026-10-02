"""Tests for MCP server commands."""

from __future__ import annotations

from typer.testing import CliRunner

from monarch_cli.commands.mcp import app

runner = CliRunner()


def test_mcp_start_check_exits() -> None:
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "MCP dependency installed" in result.stderr
    assert "MCP server constructable" in result.stderr
    assert "monarch.run" in result.stderr
    assert "monarch.auth_login" in result.stderr
