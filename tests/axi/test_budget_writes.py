"""Budget failures cannot masquerade as successful setters."""

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "command,method,field",
    [
        (
            ["set", "--category", "123", "--amount", "80"],
            "set_budget_amount",
            "updateOrCreateBudgetItem",
        ),
        (["flexible", "--amount", "80"], "update_flexible_budget", "updateOrCreateFlexBudgetItem"),
        (["reset"], "reset_budget", "resetBudget"),
        (["flex-rollover"], "update_flex_rollover_settings", "updateBudgetSettings"),
    ],
)
@pytest.mark.parametrize("payload", [None, {"errors": [{"message": "SECRET backend"}]}])
def test_budget_unconfirmed_write_is_error(command, method, field, payload):
    client = AsyncMock()
    getattr(client, method).return_value = {field: payload}
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["budgets", *command, "--json"])
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    getattr(client, method).assert_awaited_once()


def test_budget_set_requires_matching_amount():
    client = AsyncMock()
    client.set_budget_amount.return_value = {
        "updateOrCreateBudgetItem": {"budgetItem": {"id": "1", "budgetAmount": 12}}
    }
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["budgets", "set", "--category", "123", "--amount", "80", "--json"]
        )
    assert result.exit_code == 1


@pytest.mark.parametrize(
    "words",
    [
        ["set", "--category", "123", "--amount", "nan"],
        ["set", "--category", "", "--amount", "80"],
        ["flexible", "--amount", "inf"],
        ["reset", "--start", "invalid"],
        ["reset", "--start", "20261101"],
        ["flex-rollover", "--starting-balance", "nan"],
    ],
)
def test_budget_invalid_input_fails_before_auth(words):
    with patch("monarch_cli.commands.budgets.get_authenticated_client") as auth:
        result = CliRunner().invoke(app, ["budgets", *words, "--json"])
    assert result.exit_code == 2
    auth.assert_not_called()


def test_budget_network_failure_does_not_retry():
    client = AsyncMock()
    client.set_budget_amount.side_effect = TimeoutError("SECRET timeout")
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["budgets", "set", "--category", "123", "--amount", "80", "--json"]
        )
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    client.set_budget_amount.assert_awaited_once()


def test_budget_upsert_accepts_repeated_desired_amount_with_real_sdk():
    from monarchmoney import MonarchMoney

    client = MonarchMoney(token="synthetic")
    calls = []

    async def gql_call(**kwargs):
        calls.append(kwargs)
        return {
            "updateOrCreateBudgetItem": {
                "budgetItem": {"id": "1", "budgetAmount": kwargs["variables"]["input"]["amount"]}
            }
        }

    client.gql_call = gql_call
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        for _ in range(2):
            result = CliRunner().invoke(
                app, ["budgets", "set", "--category", "123", "--amount", "0", "--future", "--json"]
            )
            assert result.exit_code == 0, result.stdout
    assert calls[0]["operation"] == "Common_UpdateBudgetItem"
    assert calls[0]["variables"] == calls[1]["variables"]
    assert calls[0]["variables"]["input"]["applyToFuture"] is True


def test_reset_accepts_explicit_null_errors():
    client = AsyncMock()
    client.reset_budget.return_value = {"resetBudget": {"errors": None}}
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["budgets", "reset", "--json"])
    assert result.exit_code == 0, result.stdout


@pytest.mark.parametrize("value", [False, "invalid", [], {"startMonth": "2026-11-01"}])
def test_rollover_rejects_malformed_period(value):
    client = AsyncMock()
    client.update_flex_rollover_settings.return_value = {
        "updateBudgetSettings": {"budgetRolloverPeriod": value}
    }
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["budgets", "flex-rollover", "--json"])
    assert result.exit_code == 1


@pytest.mark.parametrize(
    "period",
    [
        {"id": "p1", "startMonth": "2020-01-01", "startingBalance": 0},
        {"id": "p1", "startMonth": "2026-11-01", "startingBalance": 99},
        None,
    ],
)
def test_enabled_rollover_requires_requested_period(period):
    client = AsyncMock()
    client.update_flex_rollover_settings.return_value = {
        "updateBudgetSettings": {"budgetRolloverPeriod": period}
    }
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app,
            [
                "budgets",
                "flex-rollover",
                "--start-month",
                "2026-11-01",
                "--starting-balance",
                "0",
                "--enabled",
                "--json",
            ],
        )
    assert result.exit_code == 1


def test_rollover_uses_real_sdk_and_resolved_month_default():
    from datetime import date

    from monarchmoney import MonarchMoney

    client = MonarchMoney(token="synthetic")

    async def gql_call(**kwargs):
        if kwargs["operation"] == "Web_GetFlexibleGroupRolloverSettings":
            return {
                "budgetSystem": "fixed_and_flex",
                "flexExpenseRolloverPeriod": {
                    "id": "p1",
                    "startMonth": date.today().replace(day=1).isoformat(),
                    "startingBalance": 0,
                },
            }
        assert kwargs["operation"] == "Web_UpdateFlexibleGroupRolloverSettings"
        values = kwargs["variables"]["input"]
        assert values["rolloverStartMonth"] == date.today().replace(day=1).isoformat()
        assert values["rolloverEnabled"] is True
        return {
            "updateBudgetSettings": {
                "budgetRolloverPeriod": {
                    "id": "p1",
                    "startMonth": values["rolloverStartMonth"],
                    "startingBalance": values["rolloverStartingBalance"],
                }
            }
        }

    client.gql_call = gql_call
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        for _ in range(2):
            result = CliRunner().invoke(app, ["budgets", "flex-rollover", "--json"])
            assert result.exit_code == 0, result.stdout
