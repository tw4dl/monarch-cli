"""Investment account retries require proof of the entire requested state."""

import json
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app

ACCOUNT = {
    "id": "101",
    "displayName": "Manual",
    "subtype": {"name": "brokerage"},
    "isManual": True,
    "manualInvestmentsTrackingMethod": "holdings",
    "includeInNetWorth": True,
    "includeBalanceInNetWorth": True,
    "holdingsCount": 1,
}
HOLDINGS = {
    "portfolio": {
        "aggregateHoldings": {
            "edges": [
                {
                    "node": {
                        "quantity": 999,
                        "security": {"id": "s1"},
                        "holdings": [{"id": "h1", "quantity": 5, "isManual": True}],
                    }
                }
            ]
        }
    }
}
WORDS = [
    "accounts",
    "create-investments",
    "--name",
    "Manual",
    "--subtype",
    "brokerage",
    "--holding",
    "s1=5",
    "--json",
]


def invoke(account, holdings):
    client = MagicMock(
        get_accounts=AsyncMock(return_value={"accounts": [account]}),
        gql_call=AsyncMock(return_value=holdings),
    )
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, WORDS)
    return result, client


def test_matching_account_is_successful_noop():
    result, client = invoke(ACCOUNT, HOLDINGS)
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["status"] == "unchanged"
    assert json.loads(result.stdout)["verified"] is True
    assert client.gql_call.await_count == 1
    assert client.gql_call.await_args.args[0] != "Common_CreateManualInvestmentsAccount"


@pytest.mark.parametrize(
    "field,value",
    [
        ("isManual", False),
        ("includeInNetWorth", False),
        ("subtype", {"name": "ira"}),
        ("manualInvestmentsTrackingMethod", "balance"),
    ],
)
def test_different_account_settings_still_refuse_duplicate(field, value):
    account = {**ACCOUNT, field: value}
    result, client = invoke(account, HOLDINGS)
    assert result.exit_code == 2
    client.gql_call.assert_not_awaited()


@pytest.mark.parametrize("quantity", [4, None, True])
def test_different_or_unknown_individual_values_do_not_use_aggregate(quantity):
    holdings = deepcopy(HOLDINGS)
    holdings["portfolio"]["aggregateHoldings"]["edges"][0]["node"]["holdings"][0]["quantity"] = (
        quantity
    )
    result, client = invoke(ACCOUNT, holdings)
    assert result.exit_code in {1, 2}
    assert client.gql_call.await_count == 1


def test_missing_holdings_cannot_confirm_noop():
    result, client = invoke(ACCOUNT, {})
    assert result.exit_code == 1
    assert client.gql_call.await_count == 1


def test_ambiguous_name_never_reads_or_writes_holdings():
    client = MagicMock(
        get_accounts=AsyncMock(return_value={"accounts": [ACCOUNT, {**ACCOUNT, "id": "102"}]}),
        gql_call=AsyncMock(),
    )
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, WORDS)
    assert result.exit_code == 2
    client.gql_call.assert_not_awaited()
    assert json.loads(result.stdout)["help"] == ["monarch accounts list"]
