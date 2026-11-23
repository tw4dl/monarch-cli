"""Rollover writes verify budget system through an independent native read."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "readback,expected",
    [
        (
            {
                "budgetSystem": "fixed_and_flex",
                "flexExpenseRolloverPeriod": {
                    "id": "p1",
                    "startMonth": "2024-02-01",
                    "startingBalance": 0,
                },
            },
            0,
        ),
        ({"budgetSystem": "category"}, 1),
        ({}, 1),
        ({"errors": ["failed"], "budgetSystem": "fixed_and_flex"}, 1),
    ],
)
def test_system_readback(readback, expected):
    client = MagicMock(
        update_flex_rollover_settings=AsyncMock(
            return_value={
                "updateBudgetSettings": {
                    "budgetRolloverPeriod": {
                        "id": "p1",
                        "startMonth": "2024-02-01",
                        "startingBalance": 0,
                    }
                }
            }
        ),
        gql_call=AsyncMock(return_value=readback),
    )
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["budgets", "flex-rollover", "--start-month", "2024-02-01", "--json"]
        )
    assert result.exit_code == expected, result.stdout
    assert client.update_flex_rollover_settings.await_count == 1
    assert client.gql_call.await_count == 1
    assert client.gql_call.await_args.kwargs["operation"] == "Web_GetFlexibleGroupRolloverSettings"
    if expected:
        assert "monarch budgets settings" in result.stdout


def test_readback_timeout_does_not_repeat_financial_write():
    from monarch_cli.core.exceptions import NetworkError

    client = MagicMock(
        update_flex_rollover_settings=AsyncMock(
            return_value={
                "updateBudgetSettings": {
                    "budgetRolloverPeriod": {
                        "id": "p1",
                        "startMonth": "2024-02-01",
                        "startingBalance": 0,
                    }
                }
            }
        ),
        gql_call=AsyncMock(side_effect=NetworkError("timeout")),
    )
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["budgets", "flex-rollover", "--start-month", "2024-02-01", "--json"]
        )
    assert result.exit_code == 1
    assert client.update_flex_rollover_settings.await_count == client.gql_call.await_count == 1
    assert "monarch budgets settings" in result.stdout


def test_blank_system_is_local_usage_error():
    with patch("monarch_cli.commands.budgets.get_authenticated_client") as auth:
        result = CliRunner().invoke(
            app, ["budgets", "flex-rollover", "--budget-system", " ", "--json"]
        )
    assert result.exit_code == 2
    auth.assert_not_called()
