"""Tests for MCP server commands."""

from __future__ import annotations

from typer.testing import CliRunner

from monarch_cli.commands.mcp import app

runner = CliRunner()


def test_mcp_start_check_exits() -> None:
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "ready" in result.stdout
    assert "monarch.run" in result.stdout
    assert "monarch.auth_login" in result.stdout
