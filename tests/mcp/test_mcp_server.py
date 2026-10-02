"""Tests for the Monarch MCP server wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from monarchmoney import RequireMFAException  # type: ignore[import-untyped]


def test_run_cli_blocks_interactive_login() -> None:
    """`auth login` is interactive; MCP wrapper should block it."""
    from monarch_cli.mcp_server import run_monarch_cli  # noqa: PLC0415

    with pytest.raises(ValueError, match="interactive"):
        run_monarch_cli(["auth", "login"])


def test_run_cli_version_works() -> None:
    """Basic CLI passthrough works for non-API commands."""
    from monarch_cli.mcp_server import run_monarch_cli  # noqa: PLC0415

    result = run_monarch_cli(["--version"], json_output=False)
    assert result["exit_code"] == 0
    assert "monarch-cli" in result["stdout"]


def test_auth_login_requires_mfa_when_prompted() -> None:
    """If Monarch requires MFA, wrapper returns a structured response."""
    from monarch_cli.mcp_server import auth_login  # noqa: PLC0415

    mm = MagicMock()
    mm.login.side_effect = RequireMFAException()

    with (
        patch("monarch_cli.mcp_server.MonarchMoney", return_value=mm),
        patch("monarch_cli.mcp_server.extract_token_from_client", return_value="tok"),
        patch("monarch_cli.mcp_server.save_session_token"),
        patch("monarch_cli.mcp_server.reset_client"),
    ):
        result = auth_login(email="u@example.com", password="pw", storage="file")

    assert result["status"] == "mfa_required"
