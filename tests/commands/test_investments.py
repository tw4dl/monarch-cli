"""Tests for investment commands."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from monarch_cli.main import app

runner = CliRunner()


def _account(
    account_id: str,
    name: str,
    *,
    type_name: str = "brokerage",
    holdings_count: int = 1,
    hidden: bool = False,
) -> dict[str, Any]:
    return {
        "id": account_id,
        "displayName": name,
        "isHidden": hidden,
        "holdingsCount": holdings_count,
        "type": {"name": type_name, "display": "Investments"},
        "subtype": {"display": "Brokerage (Taxable)"},
        "institution": {"name": "Fidelity"},
    }


def _holdings_response(ticker: str, quantity: float, total_value: float) -> dict[str, Any]:
    return {
        "portfolio": {
            "aggregateHoldings": {
                "edges": [
                    {
                        "node": {
                            "id": f"holding_{ticker}",
                            "quantity": quantity,
                            "basis": total_value - 10,
                            "totalValue": total_value,
                            "lastSyncedAt": "2026-05-19",
                            "holdings": [
                                {
                                    "id": f"security_{ticker}",
                                    "name": f"{ticker} Fund",
                                    "ticker": ticker,
                                }
                            ],
                            "security": {
                                "id": f"security_{ticker}",
                                "name": f"{ticker} Fund",
                                "ticker": ticker,
                                "currentPrice": total_value / quantity,
                                "oneDayChangePercent": 1.5,
                            },
                        }
                    }
                ]
            }
        }
    }


class TestInvestmentsHoldings:
    """Tests for 'monarch investments holdings'."""

    def test_discovers_visible_investment_accounts_with_holdings(self) -> None:
        """Holdings command discovers visible brokerage accounts with holdings."""
        mock_client = MagicMock()
        mock_client.get_accounts = AsyncMock(
            return_value={
                "accounts": [
                    _account("101", "Taxable"),
                    _account("102", "Checking", type_name="depository", holdings_count=0),
                    _account("103", "Empty Brokerage", holdings_count=0),
                    _account("104", "Hidden Brokerage", hidden=True),
                ]
            }
        )
        mock_client.get_account_holdings = AsyncMock(return_value=_holdings_response("VTI", 2, 700))

        with (
            patch(
                "monarch_cli.commands.investments.get_authenticated_client",
                return_value=mock_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["investments", "holdings", "--json"])

        assert result.exit_code == 0
        rows = json.loads(result.stdout)
        assert len(rows) == 1
        assert rows[0]["account_id"] == "101"
        assert rows[0]["account_name"] == "Taxable"
        assert rows[0]["ticker"] == "VTI"
        assert rows[0]["total_value"] == 700
        mock_client.get_account_holdings.assert_awaited_once_with(101)

    def test_specific_account_ids_are_queried_even_if_hidden(self) -> None:
        """Explicit account IDs are queried even when hidden or empty in account metadata."""
        mock_client = MagicMock()
        mock_client.get_accounts = AsyncMock(
            return_value={
                "accounts": [
                    _account("104", "Hidden Brokerage", hidden=True),
                ]
            }
        )
        mock_client.get_account_holdings = AsyncMock(
            return_value=_holdings_response("VXUS", 3, 240)
        )

        with (
            patch(
                "monarch_cli.commands.investments.get_authenticated_client",
                return_value=mock_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                ["investments", "holdings", "--account", "104", "--json"],
            )

        assert result.exit_code == 0
        rows = json.loads(result.stdout)
        assert rows[0]["account_id"] == "104"
        assert rows[0]["account_name"] == "Hidden Brokerage"
        assert rows[0]["ticker"] == "VXUS"

    def test_aggregate_combines_holdings_by_ticker(self) -> None:
        """Aggregate mode combines holdings with the same ticker."""
        mock_client = MagicMock()
        mock_client.get_accounts = AsyncMock(
            return_value={
                "accounts": [
                    _account("101", "Taxable"),
                    _account("102", "IRA"),
                ]
            }
        )
        mock_client.get_account_holdings = AsyncMock(
            side_effect=[
                _holdings_response("VTI", 2, 700),
                _holdings_response("VTI", 3, 1050),
            ]
        )

        with (
            patch(
                "monarch_cli.commands.investments.get_authenticated_client",
                return_value=mock_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["investments", "holdings", "--aggregate", "--json"])

        assert result.exit_code == 0
        rows = json.loads(result.stdout)
        assert rows == [
            {
                "ticker": "VTI",
                "name": "VTI Fund",
                "quantity": 5,
                "basis": 1730,
                "total_value": 1750,
                "accounts": 2,
            }
        ]

    def test_detailed_raw_holdings_include_provider_native_value(self) -> None:
        """Detailed mode uses the richer GraphQL query needed for currency audits."""
        mock_client = MagicMock()
        mock_client.get_accounts = AsyncMock(return_value={"accounts": [_account("101", "IBKR")]})
        mock_client.gql_call = AsyncMock(
            return_value={
                "portfolio": {
                    "aggregateHoldings": {
                        "edges": [
                            {
                                "node": {
                                    "id": "security-sk",
                                    "quantity": 50,
                                    "totalValue": 55_450_000,
                                    "holdings": [
                                        {
                                            "id": "holding-sk",
                                            "name": "SK Square Co Ltd",
                                            "quantity": 50,
                                            "value": 55_450_000,
                                            "closingPrice": 1_109_000,
                                        }
                                    ],
                                    "security": {
                                        "id": "security-sk",
                                        "ticker": "SKSQF",
                                        "currentPrice": None,
                                    },
                                }
                            }
                        ]
                    }
                }
            }
        )

        with (
            patch(
                "monarch_cli.commands.investments.get_authenticated_client",
                return_value=mock_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "investments",
                    "holdings",
                    "--account",
                    "101",
                    "--detailed",
                    "--raw",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        raw = json.loads(result.stdout)
        node = raw[0]["holdings"]["portfolio"]["aggregateHoldings"]["edges"][0]["node"]
        assert node["holdings"][0]["value"] == 55_450_000
        operation, _, variables = mock_client.gql_call.await_args.args
        assert operation == "Web_GetHoldingsDetailed"
        assert variables == {
            "input": {
                "accountIds": ["101"],
                "includeHiddenHoldings": True,
                "topMoversLimit": 4,
            }
        }
        mock_client.get_account_holdings.assert_not_called()


class TestInvestmentHoldingMutations:
    """Tests for verified manual holding mutations."""

    @staticmethod
    def _manual_holding_response(
        *,
        holding_id: str = "holding-1",
        security_id: str = "security-1",
        ticker: str = "LPKFF",
        quantity: float = 1000,
        cost_basis: float | None = 26513.25,
    ) -> dict[str, Any]:
        return {
            "portfolio": {
                "aggregateHoldings": {
                    "edges": [
                        {
                            "node": {
                                "id": security_id,
                                "quantity": quantity,
                                "basis": cost_basis,
                                "totalValue": 17280,
                                "holdings": [
                                    {
                                        "id": holding_id,
                                        "ticker": ticker,
                                        "quantity": quantity,
                                        "costBasis": cost_basis,
                                        "isManual": True,
                                    }
                                ],
                                "security": {
                                    "id": security_id,
                                    "ticker": ticker,
                                    "currentPrice": 17.28,
                                },
                            }
                        }
                    ]
                }
            }
        }

    def test_searches_securities(self) -> None:
        mock_client = MagicMock()
        mock_client.gql_call = AsyncMock(
            return_value={
                "securities": [
                    {
                        "id": "security-1",
                        "name": "LPKF Laser & Electronics SE",
                        "ticker": "LPKFF",
                        "currentPrice": 17.28,
                    }
                ]
            }
        )

        with (
            patch(
                "monarch_cli.commands.investments.get_authenticated_client",
                return_value=mock_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                ["investments", "securities", "LPKFF", "--limit", "5", "--json"],
            )

        assert result.exit_code == 0
        assert json.loads(result.stdout) == [
            {
                "id": "security-1",
                "name": "LPKF Laser & Electronics SE",
                "ticker": "LPKFF",
                "currentPrice": 17.28,
            }
        ]
        operation, _, variables = mock_client.gql_call.await_args.args
        assert operation == "SecuritySearch"
        assert variables == {"search": "LPKFF", "limit": 5, "orderByPopularity": True}

    def test_creates_holding_and_verifies_exact_readback(self) -> None:
        mock_client = MagicMock()
        mock_client.gql_call = AsyncMock(
            return_value={
                "createManualHolding": {
                    "holding": {"id": "holding-1", "ticker": "LPKFF"},
                    "errors": [],
                }
            }
        )
        mock_client.get_account_holdings = AsyncMock(return_value=self._manual_holding_response())

        with (
            patch(
                "monarch_cli.commands.investments.get_authenticated_client",
                return_value=mock_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "investments",
                    "holding",
                    "create",
                    "--account",
                    "101",
                    "--security",
                    "security-1",
                    "--quantity",
                    "1000",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["status"] == "created"
        assert payload["id"] == "holding-1"
        assert payload["verified"] is True
        assert payload["holding"]["quantity"] == 1000
        _, _, variables = mock_client.gql_call.await_args.args
        assert variables == {
            "input": {"accountId": "101", "securityId": "security-1", "quantity": 1000.0}
        }
        mock_client.get_account_holdings.assert_awaited_once_with(101)

    def test_updates_holding_and_verifies_quantity_and_cost_basis(self) -> None:
        mock_client = MagicMock()
        mock_client.gql_call = AsyncMock(
            return_value={
                "updateHolding": {
                    "holding": {"id": "holding-1", "quantity": 500},
                    "errors": [],
                }
            }
        )
        mock_client.get_account_holdings = AsyncMock(
            return_value=self._manual_holding_response(quantity=500, cost_basis=20000)
        )

        with (
            patch(
                "monarch_cli.commands.investments.get_authenticated_client",
                return_value=mock_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "investments",
                    "holding",
                    "update",
                    "holding-1",
                    "--account",
                    "101",
                    "--quantity",
                    "500",
                    "--cost-basis",
                    "20000",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["status"] == "updated"
        assert payload["verified"] is True
        assert payload["holding"]["costBasis"] == 20000
        _, _, variables = mock_client.gql_call.await_args.args
        assert variables == {"input": {"id": "holding-1", "quantity": 500.0, "costBasis": 20000.0}}

    def test_delete_holding_requires_yes_and_verifies_absence(self) -> None:
        mock_client = MagicMock()
        mock_client.gql_call = AsyncMock(
            return_value={"deleteHolding": {"deleted": True, "errors": []}}
        )
        mock_client.get_account_holdings = AsyncMock(
            return_value={"portfolio": {"aggregateHoldings": {"edges": []}}}
        )

        with (
            patch(
                "monarch_cli.commands.investments.get_authenticated_client",
                return_value=mock_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "investments",
                    "holding",
                    "delete",
                    "holding-1",
                    "--account",
                    "101",
                    "--yes",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload == {
            "status": "deleted",
            "entity": "holding",
            "id": "holding-1",
            "verified": True,
        }
        _, _, variables = mock_client.gql_call.await_args.args
        assert variables == {"id": "holding-1"}

    def test_update_requires_at_least_one_change(self) -> None:
        result = runner.invoke(
            app,
            [
                "investments",
                "holding",
                "update",
                "holding-1",
                "--account",
                "101",
                "--json",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.stdout)
        assert payload["code"] == "INVALID_INPUT"
