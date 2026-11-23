"""Holding creation validates inputs and verifies individual readback."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app

WORDS = [
    "investments",
    "holding",
    "create",
    "--account",
    "101",
    "--security",
    "s1",
    "--quantity",
    "5",
    "--json",
]


@pytest.mark.parametrize(
    "flag,value",
    [("--quantity", "nan"), ("--quantity", "inf"), ("--account", " "), ("--security", "")],
)
def test_invalid_input_before_auth(flag, value):
    words = WORDS.copy()
    words[words.index(flag) + 1] = value
    with patch("monarch_cli.commands.investments.get_authenticated_client") as auth:
        result = CliRunner().invoke(app, words)
    assert result.exit_code == 2
    auth.assert_not_called()


@pytest.mark.parametrize("quantity,expected", [(5, 0), (None, 1), (4, 1)])
def test_creation_requires_individual_quantity(quantity, expected):
    response = {
        "portfolio": {
            "aggregateHoldings": {
                "edges": [
                    {
                        "node": {
                            "quantity": 5,
                            "security": {"id": "s1"},
                            "holdings": [{"id": "h1", "quantity": quantity}],
                        }
                    }
                ]
            }
        }
    }
    client = AsyncMock()
    client.gql_call.side_effect = [
        {"createManualHolding": {"errors": [], "holding": {"id": "h1"}}},
        response,
    ]
    client.get_account_holdings.return_value = response
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, WORDS)
    assert result.exit_code == expected, result.stdout
    if expected == 0:
        assert json.loads(result.stdout)["holding"]["quantity"] == 5
    assert client.gql_call.await_count == 2
    assert client.gql_call.await_args.args[0] == "Web_GetHoldingsDetailed"
    client.get_account_holdings.assert_not_awaited()
