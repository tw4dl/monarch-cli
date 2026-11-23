"""Budget recovery reads retain the target month and expose native bucket data."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "words,method,field",
    [
        (
            ["set", "--category", "c1", "--amount", "10", "--start", "2024-02-01"],
            "set_budget_amount",
            "updateOrCreateBudgetItem",
        ),
        (
            ["flexible", "--amount", "10", "--start", "2024-02-01"],
            "update_flexible_budget",
            "updateOrCreateFlexBudgetItem",
        ),
        (["reset", "--start", "2024-02-01"], "reset_budget", "resetBudget"),
        (
            ["flex-rollover", "--start-month", "2024-02-01"],
            "update_flex_rollover_settings",
            "updateBudgetSettings",
        ),
    ],
)
@pytest.mark.parametrize("timeout", [False, True])
def test_budget_error_inspects_the_requested_month(words, method, field, timeout):
    client = AsyncMock()
    if timeout:
        getattr(client, method).side_effect = TimeoutError()
    else:
        getattr(client, method).return_value = {field: None}
    with patch("monarch_cli.commands.budgets.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["budgets", *words, "--json"])
    assert result.exit_code == 1
    expected = (
        "monarch budgets settings"
        if words[0] == "flex-rollover"
        else ("monarch budgets list --raw --start 2024-02-01 --end 2024-02-29")
    )
    assert json.loads(result.stdout)["help"] == [expected]
