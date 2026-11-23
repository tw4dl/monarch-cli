"""Missing holdings data must not claim a successful empty portfolio."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "payload", [{}, {"accounts": None}, {"errors": ["failed"], "accounts": []}]
)
def test_missing_accounts_is_error(payload):
    client = MagicMock(get_accounts=AsyncMock(return_value=payload))
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["investments", "holdings", "--json"])
    assert result.exit_code == 1
    assert "error" in result.stdout


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"portfolio": {}},
        {"portfolio": {"aggregateHoldings": {}}},
        {"portfolio": {"aggregateHoldings": {"edges": [None]}}},
    ],
)
def test_missing_holdings_is_error(payload):
    client = MagicMock(
        get_accounts=AsyncMock(
            return_value={
                "accounts": [
                    {
                        "id": "101",
                        "displayName": "Manual",
                        "type": {"name": "brokerage"},
                        "holdingsCount": 1,
                    }
                ]
            }
        ),
        get_account_holdings=AsyncMock(return_value=payload),
    )
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["investments", "holdings", "--json"])
    assert result.exit_code == 1
    assert "error" in result.stdout


def test_known_empty_holdings_succeeds():
    client = MagicMock(
        get_accounts=AsyncMock(
            return_value={
                "accounts": [
                    {
                        "id": "101",
                        "displayName": "Manual",
                        "type": {"name": "brokerage"},
                        "holdingsCount": 1,
                    }
                ]
            }
        ),
        get_account_holdings=AsyncMock(
            return_value={"portfolio": {"aggregateHoldings": {"edges": []}}}
        ),
    )
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["investments", "holdings"])
    assert result.exit_code == 0
    assert "count: 0" in result.stdout
    assert "No investments holdings results" in result.stdout
