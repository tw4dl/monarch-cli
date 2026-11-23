"""MCP diagnostics use CLI data output; the explicit server keeps its own protocol."""

import importlib.metadata
import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize("flags", [[], ["--json"]])
def test_mcp_status_is_structured(flags):
    with patch("monarch_cli.commands.mcp._load_mcp_server", return_value=MagicMock()):
        result = CliRunner().invoke(app, ["mcp", "status", *flags])
    assert result.exit_code == 0, result.output
    if flags:
        data = json.loads(result.stdout)
        assert data["status"] == "ready"
        assert data["tools"] == ["monarch.run", "monarch.auth_login"]
    else:
        assert "status: ready" in result.stdout
        assert "monarch mcp start" in result.stdout
    assert result.stderr == ""


def test_mcp_missing_dependency_is_structured_error():
    with patch(
        "monarch_cli.commands.mcp.importlib.metadata.version",
        side_effect=importlib.metadata.PackageNotFoundError,
    ):
        result = CliRunner().invoke(app, ["mcp", "status", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"] is True
    assert result.stderr == ""


def test_invalid_transport_fails_before_server_dependency():
    with patch("monarch_cli.commands.mcp._load_mcp_server") as load:
        result = CliRunner().invoke(app, ["mcp", "start", "--transport", "invalid"])
    assert result.exit_code == 2
    load.assert_not_called()
