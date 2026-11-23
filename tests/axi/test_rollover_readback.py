"""Use the native UI's period-presence contract to verify rollover state."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app

PERIOD = {"id": "p1", "startMonth": "2024-02-01", "startingBalance": 0}


@pytest.mark.parametrize(
    "period,enabled,expected",
    [
        (PERIOD, True, 0),
        (None, True, 1),
        ({}, True, 1),
        ({**PERIOD, "startMonth": "2024-01-01"}, True, 1),
        ({**PERIOD, "startingBalance": 1}, True, 1),
        ({**PERIOD, "startingBalance": False}, True, 1),
        (PERIOD, False, 1),
        (None, False, 0),
    ],
)
def test_independent_rollover_readback(period, enabled, expected):
    client = MagicMock(
        update_flex_rollover_settings=AsyncMock(
            return_value={"updateBudgetSettings": {"budgetRolloverPeriod": PERIOD}}
        ),
        gql_call=AsyncMock(
            return_value={"budgetSystem": "fixed_and_flex", "flexExpenseRolloverPeriod": period}
        ),
    )
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app,
            [
                "budgets",
                "flex-rollover",
                "--start-month",
                "2024-02-01",
                "--enabled" if enabled else "--disabled",
                "--json",
            ],
        )
    assert result.exit_code == expected, result.stdout
    assert client.update_flex_rollover_settings.await_count == client.gql_call.await_count == 1
    if expected:
        assert "monarch budgets settings" in result.stdout


def test_missing_period_is_not_the_disabled_state():
    client = MagicMock(
        update_flex_rollover_settings=AsyncMock(
            return_value={"updateBudgetSettings": {"budgetRolloverPeriod": None}}
        ),
        gql_call=AsyncMock(return_value={"budgetSystem": "fixed_and_flex"}),
    )
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["budgets", "flex-rollover", "--disabled", "--json"])
    assert result.exit_code == 1
