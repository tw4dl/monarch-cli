"""Holding setters compare individual values, never aggregate quantities."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from graphql import print_ast
from typer.testing import CliRunner

from monarch_cli.main import app


def holdings(quantity):
    return {
        "portfolio": {
            "aggregateHoldings": {
                "edges": [
                    {
                        "node": {
                            "quantity": 999,
                            "basis": 9999,
                            "holdings": [
                                {
                                    "id": "h1",
                                    "quantity": quantity,
                                    "costBasis": 40,
                                    "isManual": True,
                                }
                            ],
                            "security": {"id": "s1", "type": "stock"},
                        }
                    }
                ]
            }
        }
    }


def test_repeated_holding_setter_writes_once_and_compares_individual_quantity():
    state = {"quantity": 5}
    writes = []

    async def gql_call(operation, query, variables):
        if operation == "Web_GetHoldingsDetailed":
            assert "costBasis" in print_ast(query)
            assert variables["input"]["accountIds"] == ["101"]
            return holdings(state["quantity"])
        writes.append(variables)
        state["quantity"] = variables["input"]["quantity"]
        return {
            "updateHolding": {"errors": [], "holding": {"id": "h1", "quantity": state["quantity"]}}
        }

    client = AsyncMock()
    client.gql_call.side_effect = gql_call
    words = [
        "investments",
        "holding",
        "update",
        "h1",
        "--account",
        "101",
        "--quantity",
        "7",
        "--json",
    ]
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        first = CliRunner().invoke(app, words)
        second = CliRunner().invoke(app, words)
    assert first.exit_code == second.exit_code == 0, first.stdout + second.stdout
    assert json.loads(first.stdout)["status"] == "updated"
    assert json.loads(second.stdout)["status"] == "unchanged"
    assert len(writes) == 1


@pytest.mark.parametrize("flags", [["--quantity", "nan"], ["--cost-basis", "inf"]])
def test_invalid_holding_values_fail_before_auth(flags):
    with patch("monarch_cli.commands.investments.get_authenticated_client") as auth:
        result = CliRunner().invoke(
            app, ["investments", "holding", "update", "h1", "--account", "101", *flags, "--json"]
        )
    assert result.exit_code == 2
    auth.assert_not_called()


def test_exact_holding_values_never_fall_back_to_security_aggregate():
    from monarch_cli.commands.investments import _find_holding_by_id

    response = holdings(5)
    row = response["portfolio"]["aggregateHoldings"]["edges"][0]["node"]["holdings"][0]
    row.pop("quantity")
    row.pop("costBasis")
    found = _find_holding_by_id(response, "h1", exact_values=True)
    assert found["quantity"] is None
    assert found["costBasis"] is None
