"""Expose independently readable native settings for safe recovery."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from monarch_cli.main import app


def test_native_settings_read_preserves_json_and_no_mutation():
    payload = {"budgetSystem": "fixed_and_flex", "flexExpenseRolloverPeriod": None}
    client = MagicMock(gql_call=AsyncMock(return_value=payload))
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["budgets", "settings", "--json"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == payload
    assert client.gql_call.await_args.kwargs["operation"] == "Web_GetFlexibleGroupRolloverSettings"


def test_missing_setting_is_not_disabled():
    client = MagicMock(gql_call=AsyncMock(return_value={"budgetSystem": "fixed_and_flex"}))
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["budgets", "settings", "--json"])
    assert result.exit_code == 1, result.stdout
