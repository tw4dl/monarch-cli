"""Tests for account commands."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.commands.accounts import app
from monarch_cli.core.exceptions import NetworkError
from monarch_cli.output import set_quiet

runner = CliRunner()


@pytest.fixture
def mock_authenticated_client() -> MagicMock:
    """Create a mock authenticated client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def sample_accounts_response() -> dict:
    """Sample accounts API response."""
    return {
        "accounts": [
            {
                "id": "acc_123",
                "displayName": "Chase Checking",
                "type": {"display": "Checking"},
                "subtype": {"display": "Checking"},
                "currentBalance": 1234.56,
                "institution": {"name": "Chase"},
                "isHidden": False,
                "isManual": False,
                "updatedAt": "2024-01-15T10:30:00Z",
            },
            {
                "id": "acc_456",
                "displayName": "Savings Account",
                "type": {"display": "Savings"},
                "subtype": {"display": "Savings"},
                "currentBalance": 5000.00,
                "institution": {"name": "Ally Bank"},
                "isHidden": False,
                "isManual": True,
                "updatedAt": "2024-01-14T09:00:00Z",
            },
        ]
    }


@pytest.fixture
def transformed_accounts() -> list[dict]:
    """Expected transformed accounts."""
    return [
        {
            "id": "acc_123",
            "name": "Chase Checking",
            "type": "Checking",
            "subtype": "Checking",
            "balance": 1234.56,
            "institution": "Chase",
            "is_active": True,
            "is_manual": False,
            "last_updated": "2024-01-15T10:30:00Z",
        },
        {
            "id": "acc_456",
            "name": "Savings Account",
            "type": "Savings",
            "subtype": "Savings",
            "balance": 5000.00,
            "institution": "Ally Bank",
            "is_active": True,
            "is_manual": True,
            "last_updated": "2024-01-14T09:00:00Z",
        },
    ]


class TestAccountsList:
    """Tests for the accounts list command."""

    def test_list_returns_transformed_accounts(self, transformed_accounts: list[dict]) -> None:
        """List command returns transformed accounts."""
        with (
            patch(
                "monarch_cli.commands.accounts.list_accounts",
                return_value=transformed_accounts,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["list", "--json"])

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert len(output) == 2
            assert output[0]["id"] == "acc_123"
            assert output[0]["name"] == "Chase Checking"
            assert output[1]["id"] == "acc_456"

    def test_list_raw_returns_api_response(
        self, mock_authenticated_client: MagicMock, sample_accounts_response: dict
    ) -> None:
        """List with --raw returns raw API response."""

        async def async_accounts():
            return sample_accounts_response

        mock_authenticated_client.get_accounts = async_accounts

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["list", "--raw", "--json"])

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert "accounts" in output
            assert len(output["accounts"]) == 2

    def test_list_ndjson_outputs_one_per_line(self, transformed_accounts: list[dict]) -> None:
        """List with --ndjson outputs one JSON object per line."""
        with (
            patch(
                "monarch_cli.commands.accounts.list_accounts",
                return_value=transformed_accounts,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["list", "--ndjson"])

            assert result.exit_code == 0
            lines = result.stdout.strip().split("\n")
            assert len(lines) == 2
            assert json.loads(lines[0])["id"] == "acc_123"
            assert json.loads(lines[1])["id"] == "acc_456"

    def test_list_table_format(self, transformed_accounts: list[dict]) -> None:
        """List with --format table outputs a table."""
        with (
            patch(
                "monarch_cli.commands.accounts.list_accounts",
                return_value=transformed_accounts,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["list", "--format", "table"])

            assert result.exit_code == 0
            # Table output has table chars and column headers
            assert "id" in result.stdout
            assert "name" in result.stdout
            # Table contains box drawing characters
            assert "┃" in result.stdout or "|" in result.stdout

    def test_list_csv_format(self, transformed_accounts: list[dict]) -> None:
        """List with --format csv outputs CSV."""
        with (
            patch(
                "monarch_cli.commands.accounts.list_accounts",
                return_value=transformed_accounts,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["list", "--format", "csv"])

            assert result.exit_code == 0
            lines = result.stdout.strip().split("\n")
            assert len(lines) == 3  # header + 2 accounts
            assert "id" in lines[0]  # header
            assert "acc_123" in lines[1]

    def test_list_handles_empty_accounts(self) -> None:
        """List handles case with no accounts."""
        with (
            patch(
                "monarch_cli.commands.accounts.list_accounts",
                return_value=[],
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["list", "--json"])

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output == []

    def test_list_quiet_mode_outputs_ids_only(self, transformed_accounts: list[dict]) -> None:
        """List with quiet mode outputs only account IDs."""
        with (
            patch(
                "monarch_cli.commands.accounts.list_accounts",
                return_value=transformed_accounts,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            # Set quiet mode globally (simulates --quiet flag)
            set_quiet(True)
            try:
                result = runner.invoke(app, ["list"])

                assert result.exit_code == 0
                lines = result.stdout.strip().split("\n")
                assert len(lines) == 2
                assert lines[0] == "acc_123"
                assert lines[1] == "acc_456"
            finally:
                set_quiet(False)  # Cleanup

    def test_list_quiet_mode_empty_list(self) -> None:
        """Quiet mode with empty list produces no output."""
        with (
            patch(
                "monarch_cli.commands.accounts.list_accounts",
                return_value=[],
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            set_quiet(True)
            try:
                result = runner.invoke(app, ["list"])

                assert result.exit_code == 0
                assert result.stdout.strip() == ""
            finally:
                set_quiet(False)

    def test_list_help_shows_examples(self) -> None:
        """List --help shows examples."""
        result = runner.invoke(app, ["list", "--help"])

        assert result.exit_code == 0
        # Strip ANSI codes for comparison
        output = result.stdout.replace("\x1b[1m", "").replace("\x1b[0m", "")
        assert "monarch accounts list" in output
        assert "json" in output.lower()
        assert "format" in output.lower()


class TestAccountsRefresh:
    """Tests for the accounts refresh command."""

    def test_refresh_all_accounts(self) -> None:
        """Refresh without args refreshes all accounts."""
        refresh_result = {
            "status": "ok",
            "account_count": 3,
            "message": "Refresh requested for 3 account(s)",
        }

        with (
            patch(
                "monarch_cli.commands.accounts.refresh_accounts",
                return_value=refresh_result,
            ) as mock_refresh,
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["refresh"])

            assert result.exit_code == 0
            mock_refresh.assert_called_once_with(None)
            output = json.loads(result.stdout)
            assert output["status"] == "ok"
            assert output["account_count"] == 3

    def test_refresh_specific_accounts(self) -> None:
        """Refresh with -a flags refreshes specific accounts."""
        refresh_result = {
            "status": "ok",
            "account_count": 2,
            "message": "Refresh requested for 2 account(s)",
        }

        with (
            patch(
                "monarch_cli.commands.accounts.refresh_accounts",
                return_value=refresh_result,
            ) as mock_refresh,
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["refresh", "-a", "acc_123", "-a", "acc_456"])

            assert result.exit_code == 0
            mock_refresh.assert_called_once_with(["acc_123", "acc_456"])

    def test_refresh_no_accounts(self) -> None:
        """Refresh handles no accounts case."""
        refresh_result = {
            "status": "no_accounts",
            "account_count": 0,
            "message": "No accounts found to refresh",
        }

        with (
            patch(
                "monarch_cli.commands.accounts.refresh_accounts",
                return_value=refresh_result,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["refresh"])

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["status"] == "no_accounts"

    def test_refresh_help_shows_examples(self) -> None:
        """Refresh --help shows examples."""
        result = runner.invoke(app, ["refresh", "--help"])

        assert result.exit_code == 0
        # Strip ANSI codes for comparison
        output = result.stdout.replace("\x1b[1m", "").replace("\x1b[0m", "")
        assert "monarch accounts refresh" in output
        assert "account" in output.lower()

    def test_refresh_waits_when_requested(self, mock_authenticated_client: MagicMock) -> None:
        """Refresh --wait calls the wait-capable API."""
        captured: dict = {}

        async def async_refresh_and_wait(**kwargs):
            captured.update(kwargs)
            return True

        mock_authenticated_client.request_accounts_refresh_and_wait = async_refresh_and_wait

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                ["refresh", "-a", "acc_123", "--wait", "--timeout", "120", "--delay", "5"],
            )

            assert result.exit_code == 0
            assert captured == {"account_ids": ["acc_123"], "timeout": 120, "delay": 5}
            assert json.loads(result.stdout)["status"] == "complete"

    def test_refresh_wait_uses_timeout_buffer(self, mock_authenticated_client: MagicMock) -> None:
        """Refresh --wait gives the client wait loop headroom beyond timeout + delay."""

        async def async_refresh_and_wait(**_: object) -> bool:
            return True

        mock_authenticated_client.request_accounts_refresh_and_wait = async_refresh_and_wait

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch(
                "monarch_cli.commands.accounts.run_api_call", return_value=True
            ) as mock_run_api_call,
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "refresh",
                    "-a",
                    "acc_123",
                    "--wait",
                    "--timeout",
                    "120",
                    "--delay",
                    "5",
                    "--json",
                ],
            )

            assert result.exit_code == 0
            assert mock_run_api_call.call_args.kwargs["timeout_seconds"] == 155

    def test_refresh_wait_timeout_falls_back_to_refresh_status(
        self, mock_authenticated_client: MagicMock
    ) -> None:
        """Refresh --wait reports timeout when the outer wait expires with incomplete status."""

        timed_out_wait = NetworkError(
            message="Request timed out after 155s (1 attempts)",
            details={"timeout_seconds": 155, "attempts": 1},
        )

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch(
                "monarch_cli.commands.accounts.run_api_call",
                side_effect=[timed_out_wait, False],
            ) as mock_run_api_call,
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "refresh",
                    "-a",
                    "acc_123",
                    "--wait",
                    "--timeout",
                    "120",
                    "--delay",
                    "5",
                    "--json",
                ],
            )

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["status"] == "timeout"
            assert output["complete"] is False
            assert output["wait_error"]["code"] == "NETWORK_ERROR"
            assert mock_run_api_call.call_count == 2

    def test_refresh_wait_timeout_falls_back_to_complete_when_status_caught_up(
        self, mock_authenticated_client: MagicMock
    ) -> None:
        """Refresh --wait returns complete when fallback status shows the refresh finished."""

        timed_out_wait = NetworkError(
            message="Request timed out after 155s (1 attempts)",
            details={"timeout_seconds": 155, "attempts": 1},
        )

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch(
                "monarch_cli.commands.accounts.run_api_call",
                side_effect=[timed_out_wait, True],
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "refresh",
                    "-a",
                    "acc_123",
                    "--wait",
                    "--timeout",
                    "120",
                    "--delay",
                    "5",
                    "--json",
                ],
            )

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["status"] == "complete"
            assert output["complete"] is True

    def test_refresh_accepts_local_json_flag(self) -> None:
        """Refresh accepts subcommand-local --json for script consistency."""
        refresh_result = {"status": "ok", "account_count": 1}

        with (
            patch(
                "monarch_cli.commands.accounts.refresh_accounts",
                return_value=refresh_result,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["refresh", "--json"])

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["entity"] == "account"
            assert output["status"] == "ok"
            assert output["result"] == refresh_result


class TestAccountsApiCoverage:
    """Tests for API-backed account workflows."""

    def test_history_calls_account_history(self, mock_authenticated_client: MagicMock) -> None:
        """Account history command calls get_account_history."""

        async def async_history(account_id: int):
            return {"account_id": account_id, "history": []}

        mock_authenticated_client.get_account_history = async_history

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["history", "123", "--json"])

            assert result.exit_code == 0
            assert json.loads(result.stdout)["account_id"] == 123

    def test_create_manual_account(self, mock_authenticated_client: MagicMock) -> None:
        """Manual account creation maps CLI options to API args."""
        captured: dict = {}

        async def async_create(**kwargs):
            captured.update(kwargs)
            return {"id": "acc_manual"}

        mock_authenticated_client.create_manual_account = async_create

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "create",
                    "--name",
                    "Cash",
                    "--type",
                    "cash",
                    "--subtype",
                    "cash",
                    "--balance",
                    "42.50",
                    "--exclude-from-net-worth",
                    "--json",
                ],
            )

            assert result.exit_code == 0
            assert captured == {
                "account_type": "cash",
                "account_sub_type": "cash",
                "is_in_net_worth": False,
                "account_name": "Cash",
                "account_balance": 42.50,
            }
            output = json.loads(result.stdout)
            assert output["id"] == "acc_manual"
            assert output["entity"] == "account"
            assert output["status"] == "created"

    def test_create_manual_investments_account_with_holdings(
        self, mock_authenticated_client: MagicMock
    ) -> None:
        """Investment account creation sends initial holdings and verifies account mode."""
        mock_authenticated_client.gql_call = AsyncMock(
            return_value={
                "createManualInvestmentsAccount": {
                    "account": {"id": "acc_investments"},
                    "errors": [],
                }
            }
        )
        mock_authenticated_client.update_account = AsyncMock(return_value={"success": True})
        mock_authenticated_client.get_accounts = AsyncMock(
            side_effect=[
                {"accounts": []},
                {
                    "accounts": [
                        {
                            "id": "acc_investments",
                            "displayName": "IBKR Clean",
                            "isManual": True,
                            "manualInvestmentsTrackingMethod": "holdings",
                            "includeInNetWorth": False,
                            "includeBalanceInNetWorth": False,
                            "holdingsCount": 2,
                        }
                    ]
                },
            ]
        )

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "create-investments",
                    "--name",
                    "IBKR Clean",
                    "--subtype",
                    "brokerage",
                    "--holding",
                    "security-1=1000",
                    "--holding",
                    "security-2=500",
                    "--exclude-from-net-worth",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["status"] == "created"
        assert payload["id"] == "acc_investments"
        assert payload["verified"] is True
        assert payload["initial_holding_count"] == 2
        operation, _, variables = mock_authenticated_client.gql_call.await_args.args
        assert operation == "Common_CreateManualInvestmentsAccount"
        assert variables == {
            "input": {
                "name": "IBKR Clean",
                "subtype": "brokerage",
                "manualInvestmentsTrackingMethod": "holdings",
                "initialHoldings": [
                    {"securityId": "security-1", "quantity": 1000.0},
                    {"securityId": "security-2", "quantity": 500.0},
                ],
            }
        }
        mock_authenticated_client.update_account.assert_awaited_once_with(
            account_id="acc_investments",
            include_in_net_worth=False,
        )

    def test_create_investments_rejects_malformed_holding(self) -> None:
        """Initial holding options require security_id=quantity syntax."""
        result = runner.invoke(
            app,
            [
                "create-investments",
                "--name",
                "IBKR Clean",
                "--subtype",
                "brokerage",
                "--holding",
                "security-without-quantity",
                "--json",
            ],
        )

        assert result.exit_code == 2
        payload = json.loads(result.stdout)
        assert payload["code"] == "INVALID_INPUT"

    def test_create_investments_refuses_duplicate_name(
        self, mock_authenticated_client: MagicMock
    ) -> None:
        """Retrying investment account creation cannot create an exact-name duplicate."""
        mock_authenticated_client.get_accounts = AsyncMock(
            return_value={
                "accounts": [
                    {"id": "existing-1", "displayName": "IBKR Clean"},
                ]
            }
        )

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "create-investments",
                    "--name",
                    "IBKR Clean",
                    "--subtype",
                    "brokerage",
                    "--json",
                ],
            )

        assert result.exit_code == 2
        payload = json.loads(result.stdout)
        assert payload["code"] == "INVALID_INPUT"
        assert payload["details"]["account_ids"] == ["existing-1"]
        mock_authenticated_client.gql_call.assert_not_called()

    def test_update_account_metadata(self, mock_authenticated_client: MagicMock) -> None:
        """Account update sends only requested fields."""
        captured: dict = {}

        async def async_update(**kwargs):
            captured.update(kwargs)
            return {"success": True}

        mock_authenticated_client.update_account = async_update

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                ["update", "acc_123", "--name", "Brokerage", "--balance", "100", "--json"],
            )

            assert result.exit_code == 0
            assert captured == {
                "account_id": "acc_123",
                "account_name": "Brokerage",
                "account_balance": 100.0,
            }
            output = json.loads(result.stdout)
            assert output["id"] == "acc_123"
            assert output["entity"] == "account"
            assert output["status"] == "updated"

    def test_delete_requires_yes(self) -> None:
        """Account delete is guarded."""
        result = runner.invoke(app, ["delete", "acc_123"])

        assert result.exit_code == 1
        assert "requires --yes" in result.stdout

    def test_delete_accepts_local_json_flag(self, mock_authenticated_client: MagicMock) -> None:
        """Account delete accepts --json and emits a normalized envelope."""

        async def async_delete(account_id: str):
            return {"deleted": account_id}

        mock_authenticated_client.delete_account = async_delete

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["delete", "acc_123", "--yes", "--json"])

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["id"] == "acc_123"
            assert output["entity"] == "account"
            assert output["status"] == "deleted"
            assert output["result"] == {"deleted": "acc_123"}

    def test_upload_history_accepts_local_json_flag(
        self, mock_authenticated_client: MagicMock, tmp_path
    ) -> None:
        """Upload history accepts --json and emits a normalized envelope."""
        csv_path = tmp_path / "history.csv"
        csv_path.write_text("date,amount\n2024-01-01,123.45\n")

        async def async_upload(**_kwargs):
            return True

        mock_authenticated_client.upload_account_balance_history = async_upload

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["upload-history", "acc_123", str(csv_path), "--json"])

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["id"] == "acc_123"
            assert output["entity"] == "account"
            assert output["status"] == "uploaded"
            assert output["rows"] == 1

    def test_clone_filtered_dry_run_summarizes_kept_and_excluded(
        self,
        mock_authenticated_client: MagicMock,
    ) -> None:
        """Clone dry-run reports filtered counts and opening balance."""

        async def async_accounts():
            return {
                "accounts": [
                    {
                        "id": "src_1",
                        "displayName": "Checking Source",
                        "type": {"name": "depository", "display": "Checking"},
                        "subtype": {"name": "checking", "display": "Checking"},
                        "currentBalance": 1000.0,
                    }
                ]
            }

        async def async_transactions(**kwargs):
            if kwargs.get("account_ids") == ["acc_new"]:
                return {"allTransactions": {"results": []}}
            return {
                "allTransactions": {
                    "results": [
                        {
                            "id": "txn_keep",
                            "date": "2026-07-01",
                            "amount": 100.0,
                            "plaidName": "AAPL BUY",
                            "merchant": {"name": "AAPL BUY"},
                            "category": {"id": "cat_invest", "name": "Transfer"},
                        },
                        {
                            "id": "txn_fx",
                            "date": "2026-07-02",
                            "amount": -5.0,
                            "plaidName": "USD.TWD",
                            "merchant": {"name": "usd.twd"},
                            "category": {"id": "cat_fx", "name": "FX Conversion"},
                        },
                        {
                            "id": "txn_int",
                            "date": "2026-07-03",
                            "amount": 0.2,
                            "plaidName": "USD CREDIT INT",
                            "merchant": {"name": "Usd Credit Int for Jun 2026"},
                            "category": {"id": "cat_transfer", "name": "Transfer"},
                        },
                    ]
                }
            }

        mock_authenticated_client.get_accounts = async_accounts
        mock_authenticated_client.get_transactions = async_transactions

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "clone-filtered",
                    "src_1",
                    "--name",
                    "IBKR Clean",
                    "--dry-run",
                    "--json",
                ],
            )

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["status"] == "dry_run"
            assert output["clone_mode"] == "transaction_replay"
            assert output["kept_transaction_count"] == 1
            assert output["excluded_transaction_count"] == 2
            assert output["opening_balance"] == 900.0

    def test_clone_filtered_creates_manual_account_and_replays_kept_rows(
        self,
        mock_authenticated_client: MagicMock,
    ) -> None:
        """Clone create path builds a manual account and replays kept transactions."""
        created_transactions: list[dict] = []
        created_account: dict = {}

        async def async_accounts():
            return {
                "accounts": [
                    {
                        "id": "src_1",
                        "displayName": "Checking Source",
                        "type": {"name": "depository", "display": "Checking"},
                        "subtype": {"name": "checking", "display": "Checking"},
                        "currentBalance": 1000.0,
                    }
                ]
            }

        async def async_transactions(**kwargs):
            if kwargs.get("account_ids") == ["acc_new"]:
                return {"allTransactions": {"results": []}}
            return {
                "allTransactions": {
                    "results": [
                        {
                            "id": "txn_keep",
                            "date": "2026-07-01",
                            "amount": 100.0,
                            "plaidName": "AAPL BUY",
                            "merchant": {"name": "AAPL BUY"},
                            "category": {"id": "cat_invest", "name": "Transfer"},
                            "notes": "kept",
                        },
                        {
                            "id": "txn_fx",
                            "date": "2026-07-02",
                            "amount": -5.0,
                            "plaidName": "USD.TWD",
                            "merchant": {"name": "usd.twd"},
                            "category": {"id": "cat_fx", "name": "FX Conversion"},
                            "notes": "drop",
                        },
                    ]
                }
            }

        async def async_create_manual_account(**kwargs):
            created_account.update(kwargs)
            return {"id": "acc_new"}

        async def async_create_transaction(**kwargs):
            created_transactions.append(kwargs)
            return {"createTransaction": {"transaction": {"id": f"tx_{len(created_transactions)}"}}}

        async def async_get_transaction_details(**_kwargs):
            return {
                "transaction": {
                    "id": "tx_1",
                    "date": "2026-07-01",
                    "amount": 100.0,
                    "notes": "kept",
                    "category": {"id": "cat_invest", "name": "Transfer"},
                    "account": {"id": "acc_new", "displayName": "IBKR Clean"},
                    "merchant": {"name": "AAPL BUY"},
                }
            }

        mock_authenticated_client.get_accounts = async_accounts
        mock_authenticated_client.get_transactions = async_transactions
        mock_authenticated_client.create_manual_account = async_create_manual_account
        mock_authenticated_client.create_transaction = async_create_transaction
        mock_authenticated_client.get_transaction_details = async_get_transaction_details

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "clone-filtered",
                    "src_1",
                    "--name",
                    "IBKR Clean",
                    "--json",
                ],
            )

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["status"] == "created"
            assert output["target_account_id"] == "acc_new"
            assert output["created_transaction_count"] == 1
            assert created_account == {
                "account_type": "depository",
                "account_sub_type": "checking",
                "is_in_net_worth": True,
                "account_name": "IBKR Clean",
                "account_balance": 900.0,
            }
            assert created_transactions == [
                {
                    "date": "2026-07-01",
                    "account_id": "acc_new",
                    "amount": 100.0,
                    "merchant_name": "AAPL BUY",
                    "category_id": "cat_invest",
                    "notes": "kept",
                    "update_balance": True,
                }
            ]

    def test_clone_filtered_brokerage_dry_run_replays_key_usd_activity(
        self,
        mock_authenticated_client: MagicMock,
        tmp_path,
    ) -> None:
        """Brokerage clones keep trades and material activity with USD overrides."""
        overrides_path = tmp_path / "normalization.csv"
        overrides_path.write_text(
            "source_transaction_id,amount,category_id,notes\n"
            "trade_raw,-1500.00,cat_buy,FX: -2000000 KRW -> -1500.00 USD; rate 0.00075.\n"
            "interest_material,98.13,cat_interest,Sign: corrected USD credit interest.\n"
        )

        async def async_accounts():
            return {
                "accounts": [
                    {
                        "id": "101",
                        "displayName": "Interactive Broker Yu Individual (...6191)",
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": 178484.81,
                    },
                    {
                        "id": "acc_clean",
                        "displayName": "IBKR Clean",
                        "isManual": True,
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": 178484.81,
                    },
                ]
            }

        async def async_transactions(**kwargs):
            if kwargs.get("account_ids") == ["acc_clean"]:
                return {"allTransactions": {"results": []}}
            return {
                "allTransactions": {
                    "results": [
                        {
                            "id": "trade_note",
                            "date": "2026-07-01",
                            "amount": -1000000.0,
                            "plaidName": "SK SQUARE CO LTD",
                            "merchant": {"name": "SK Square"},
                            "category": {"id": "cat_buy", "name": "Buy"},
                            "notes": "FX: -1000000 KRW -> -750.00 USD; rate 0.00075.",
                        },
                        {
                            "id": "trade_raw",
                            "date": "2026-07-02",
                            "amount": -2000000.0,
                            "plaidName": "SK SQUARE CO LTD",
                            "merchant": {"name": "SK Square"},
                            "category": {"id": "cat_buy", "name": "Buy"},
                        },
                        {
                            "id": "fx_noise",
                            "date": "2026-07-02",
                            "amount": -1500.0,
                            "plaidName": "USD.KRW",
                            "merchant": {"name": "USD.KRW"},
                            "category": {"id": "cat_fx", "name": "FX Conversion"},
                        },
                        {
                            "id": "trade_without_usd_evidence",
                            "date": "2026-07-02",
                            "amount": -2500000.0,
                            "plaidName": "NEW FOREIGN SECURITY",
                            "merchant": {"name": "New Foreign Security"},
                            "category": {"id": "cat_buy", "name": "Buy"},
                        },
                        {
                            "id": "cash_transfer",
                            "date": "2026-07-03",
                            "amount": 100000.0,
                            "plaidName": "CASH RECEIPTS / ELECTRONIC FUND TRANSFERS",
                            "merchant": {"name": "Ally Savings"},
                            "category": {"id": "cat_transfer", "name": "Transfer"},
                        },
                        {
                            "id": "interest_tiny",
                            "date": "2026-07-04",
                            "amount": 0.5,
                            "plaidName": "USD CREDIT INT",
                            "merchant": {"name": "USD Credit Int"},
                            "category": {"id": "cat_interest", "name": "Interest"},
                        },
                        {
                            "id": "interest_material",
                            "date": "2026-07-05",
                            "amount": -98.13,
                            "plaidName": "USD CREDIT INT",
                            "merchant": {"name": "USD Credit Int"},
                            "category": {"id": "cat_transfer", "name": "Transfer"},
                        },
                        {
                            "id": "foreign_interest_without_usd_evidence",
                            "date": "2026-07-05",
                            "amount": 459.0,
                            "plaidName": "JPY DEBIT INT",
                            "merchant": {"name": "JPY Debit Int"},
                            "category": {"id": "cat_transfer", "name": "Transfer"},
                        },
                        {
                            "id": "fee_noise",
                            "date": "2026-07-06",
                            "amount": -0.01,
                            "plaidName": "TDCC CUSTODY FEE",
                            "merchant": {"name": "TDCC Custody Fee"},
                            "category": {"id": "cat_fee", "name": "Financial Fees"},
                        },
                    ]
                }
            }

        mock_authenticated_client.get_accounts = async_accounts
        mock_authenticated_client.get_transactions = async_transactions

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "clone-filtered",
                    "101",
                    "--name",
                    "IBKR Clean",
                    "--target-account",
                    "acc_clean",
                    "--normalization-csv",
                    str(overrides_path),
                    "--min-interest-amount",
                    "10",
                    "--dry-run",
                    "--json",
                ],
            )

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["status"] == "dry_run"
            assert output["clone_mode"] == "brokerage_ledger"
            assert output["target_account_id"] == "acc_clean"
            assert output["target_account_status"] == "existing"
            assert output["kept_transaction_count"] == 4
            assert output["excluded_transaction_count"] == 5
            assert output["normalized_transaction_count"] == 3
            assert output["excluded_reason_counts"]["missing_usd_evidence"] == 2
            assert [row["amount"] for row in output["kept_transactions"]] == [
                -750.0,
                -1500.0,
                100000.0,
                98.13,
            ]

    def test_clone_filtered_brokerage_defaults_to_excluded_from_net_worth(
        self,
        mock_authenticated_client: MagicMock,
    ) -> None:
        """A brokerage mirror must not double-count its linked source balance."""
        created_account: dict = {}

        async def async_accounts():
            return {
                "accounts": [
                    {
                        "id": "101",
                        "displayName": "IBKR Source",
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": 5000.0,
                    }
                ]
            }

        async def async_transactions(**_kwargs):
            return {"allTransactions": {"results": []}}

        async def async_create_manual_account(**kwargs):
            created_account.update(kwargs)
            return {"id": "target"}

        async def async_history(_account_id: int):
            return []

        mock_authenticated_client.get_accounts = async_accounts
        mock_authenticated_client.get_transactions = async_transactions
        mock_authenticated_client.create_manual_account = async_create_manual_account
        mock_authenticated_client.get_account_history = async_history

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                ["clone-filtered", "101", "--name", "IBKR Clean", "--json"],
            )

        assert result.exit_code == 0
        assert created_account["is_in_net_worth"] is False

    def test_clone_filtered_brokerage_reuses_target_without_changing_balance(
        self,
        mock_authenticated_client: MagicMock,
    ) -> None:
        """Brokerage replay reuses one target and creates balance-neutral rows."""
        created_transactions: list[dict] = []

        async def async_accounts():
            return {
                "accounts": [
                    {
                        "id": "101",
                        "displayName": "IBKR Source",
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": 5000.0,
                    },
                    {
                        "id": "202",
                        "displayName": "IBKR Clean",
                        "isManual": True,
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": 5000.0,
                    },
                ]
            }

        async def async_transactions(**kwargs):
            if kwargs.get("account_ids") == ["202"]:
                return {"allTransactions": {"results": []}}
            return {
                "allTransactions": {
                    "results": [
                        {
                            "id": "trade_1",
                            "date": "2026-07-01",
                            "amount": -750.0,
                            "plaidName": "SK SQUARE CO LTD",
                            "merchant": {"name": "SK Square"},
                            "category": {"id": "cat_buy", "name": "Buy"},
                            "notes": "FX: -1000000 KRW -> -750.00 USD.",
                        },
                        {
                            "id": "transfer_1",
                            "date": "2026-07-02",
                            "amount": 10000.0,
                            "plaidName": "CASH RECEIPTS",
                            "merchant": {"name": "Cash Receipts"},
                            "category": {"id": "cat_transfer", "name": "Transfer"},
                        },
                    ]
                }
            }

        async def async_create_transaction(**kwargs):
            created_transactions.append(kwargs)
            return {"createTransaction": {"transaction": {"id": "cloned_1"}}}

        async def async_get_transaction_details(**_kwargs):
            return {"transaction": {"id": "cloned_1"}}

        async def async_history(_account_id: int):
            return [{"date": "2026-07-27", "signedBalance": 5000.0}]

        async def fail_create_account(**_kwargs):
            raise AssertionError("existing target must be reused")

        mock_authenticated_client.get_accounts = async_accounts
        mock_authenticated_client.get_transactions = async_transactions
        mock_authenticated_client.create_transaction = async_create_transaction
        mock_authenticated_client.get_transaction_details = async_get_transaction_details
        mock_authenticated_client.get_account_history = async_history
        mock_authenticated_client.create_manual_account = fail_create_account

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "clone-filtered",
                    "101",
                    "--name",
                    "IBKR Clean",
                    "--target-account",
                    "202",
                    "--max-writes",
                    "1",
                    "--json",
                ],
            )

            assert result.exit_code == 0
            output = json.loads(result.stdout)
            assert output["status"] == "partial"
            assert output["target_account_id"] == "202"
            assert output["created_transaction_count"] == 1
            assert output["deferred_transaction_count"] == 1
            assert created_transactions == [
                {
                    "date": "2026-07-01",
                    "account_id": "202",
                    "amount": -750.0,
                    "merchant_name": "SK Square",
                    "category_id": "cat_buy",
                    "notes": "FX: -1000000 KRW -> -750.00 USD. Source IBKR transaction trade_1.",
                    "update_balance": False,
                }
            ]

    def test_clone_filtered_brokerage_syncs_existing_target_history(
        self,
        mock_authenticated_client: MagicMock,
    ) -> None:
        """An ongoing clone uploads source history when the target has fallen behind."""
        uploaded: dict = {}
        target_balance = 5000.0

        async def async_accounts():
            return {
                "accounts": [
                    {
                        "id": "101",
                        "displayName": "IBKR Source",
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": 6000.0,
                    },
                    {
                        "id": "202",
                        "displayName": "IBKR Clean",
                        "isManual": True,
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": target_balance,
                    },
                ]
            }

        async def async_transactions(**_kwargs):
            return {"allTransactions": {"results": []}}

        async def async_history(account_id: int):
            if account_id == 101:
                return [{"date": "2026-07-27", "signedBalance": 6000.0}]
            return [{"date": "2026-07-26", "signedBalance": 5000.0}]

        async def async_upload(**kwargs):
            nonlocal target_balance
            uploaded.update(kwargs)
            target_balance = 6000.0
            return True

        mock_authenticated_client.get_accounts = async_accounts
        mock_authenticated_client.get_transactions = async_transactions
        mock_authenticated_client.get_account_history = async_history
        mock_authenticated_client.upload_account_balance_history = async_upload

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "clone-filtered",
                    "101",
                    "--name",
                    "IBKR Clean",
                    "--target-account",
                    "202",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["balance_history_sync_required"] is True
        assert output["uploaded_history_rows"] == 1
        assert uploaded["account_id"] == "202"
        assert len(uploaded["csv_content"]) == 1

    def test_clone_filtered_brokerage_dedupes_by_source_transaction_id(
        self,
        mock_authenticated_client: MagicMock,
    ) -> None:
        """Mutable note or amount drift must not duplicate an already cloned row."""
        updated: dict = {}

        async def async_accounts():
            return {
                "accounts": [
                    {
                        "id": "101",
                        "displayName": "IBKR Source",
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": 5000.0,
                    },
                    {
                        "id": "202",
                        "displayName": "IBKR Clean",
                        "isManual": True,
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": 5000.0,
                    },
                ]
            }

        async def async_transactions(**kwargs):
            if kwargs.get("account_ids") == ["202"]:
                return {
                    "allTransactions": {
                        "results": [
                            {
                                "id": "cloned_1",
                                "date": "2026-07-01",
                                "amount": -700.0,
                                "merchant": {"name": "SK Square"},
                                "category": {"id": "cat_buy", "name": "Buy"},
                                "notes": "Older evidence. Source IBKR transaction trade_1.",
                            }
                        ]
                    }
                }
            return {
                "allTransactions": {
                    "results": [
                        {
                            "id": "trade_1",
                            "date": "2026-07-01",
                            "amount": -750.0,
                            "plaidName": "SK SQUARE CO LTD",
                            "merchant": {"name": "SK Square"},
                            "category": {"id": "cat_buy", "name": "Buy"},
                            "notes": "FX: -1000000 KRW -> -750.00 USD.",
                        }
                    ]
                }
            }

        async def async_history(_account_id: int):
            return [{"date": "2026-07-27", "signedBalance": 5000.0}]

        async def fail_create_transaction(**_kwargs):
            raise AssertionError("existing source transaction must not be cloned twice")

        async def async_update_transaction(**kwargs):
            updated.update(kwargs)
            return {"updateTransaction": {"transaction": {"id": "cloned_1"}}}

        async def async_transaction_details(**_kwargs):
            return {
                "transaction": {
                    "id": "cloned_1",
                    "date": "2026-07-01",
                    "amount": -750.0,
                    "merchant": {"name": "SK Square"},
                    "category": {"id": "cat_buy", "name": "Buy"},
                    "notes": ("FX: -1000000 KRW -> -750.00 USD. Source IBKR transaction trade_1."),
                }
            }

        mock_authenticated_client.get_accounts = async_accounts
        mock_authenticated_client.get_transactions = async_transactions
        mock_authenticated_client.get_account_history = async_history
        mock_authenticated_client.create_transaction = fail_create_transaction
        mock_authenticated_client.update_transaction = async_update_transaction
        mock_authenticated_client.get_transaction_details = async_transaction_details

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                [
                    "clone-filtered",
                    "101",
                    "--name",
                    "IBKR Clean",
                    "--target-account",
                    "202",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["status"] == "populated"
        assert output["created_transaction_count"] == 0
        assert output["existing_transaction_count"] == 1
        assert output["updated_transaction_count"] == 1
        assert output["drifted_transaction_count"] == 1
        assert output["drifted_transactions"][0]["source_transaction_id"] == "trade_1"
        assert updated == {
            "transaction_id": "cloned_1",
            "amount": -750.0,
            "merchant_name": "SK Square",
            "category_id": "cat_buy",
            "notes": ("FX: -1000000 KRW -> -750.00 USD. Source IBKR transaction trade_1."),
            "date": "2026-07-01",
        }

    def test_clone_filtered_rejects_ambiguous_duplicate_target_names(
        self,
        mock_authenticated_client: MagicMock,
    ) -> None:
        """Clone refuses to create or choose among duplicate exact-name targets."""

        async def async_accounts():
            return {
                "accounts": [
                    {
                        "id": "src",
                        "displayName": "IBKR Source",
                        "type": {"name": "brokerage", "display": "Investments"},
                        "subtype": {"name": "brokerage", "display": "Brokerage (Taxable)"},
                        "currentBalance": 5000.0,
                    },
                    {"id": "duplicate_1", "displayName": "IBKR Clean", "isManual": True},
                    {"id": "duplicate_2", "displayName": "IBKR Clean", "isManual": True},
                ]
            }

        mock_authenticated_client.get_accounts = async_accounts

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(
                app,
                ["clone-filtered", "src", "--name", "IBKR Clean", "--dry-run", "--json"],
            )

            assert result.exit_code != 0
            assert "duplicate_1" in result.stdout
            assert "duplicate_2" in result.stdout

    def test_recent_balances_calls_api(self, mock_authenticated_client: MagicMock) -> None:
        """Recent balances command calls get_recent_account_balances."""
        captured: dict = {}

        async def async_recent(**kwargs):
            captured.update(kwargs)
            return {"balances": []}

        mock_authenticated_client.get_recent_account_balances = async_recent

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["recent-balances", "--start", "2024-01-01", "--json"])

            assert result.exit_code == 0
            assert captured == {"start_date": "2024-01-01"}

    def test_refresh_status_calls_api(self, mock_authenticated_client: MagicMock) -> None:
        """Refresh status command calls is_accounts_refresh_complete."""
        captured: dict = {}

        async def async_status(**kwargs):
            captured.update(kwargs)
            return False

        mock_authenticated_client.is_accounts_refresh_complete = async_status

        with (
            patch(
                "monarch_cli.commands.accounts.get_authenticated_client",
                return_value=mock_authenticated_client,
            ),
            patch("monarch_cli.output.progress.is_interactive", return_value=False),
        ):
            result = runner.invoke(app, ["refresh-status", "-a", "acc_123", "--json"])

            assert result.exit_code == 0
            assert captured == {"account_ids": ["acc_123"]}
            assert json.loads(result.stdout)["complete"] is False


class TestAccountsApp:
    """Tests for the accounts app structure."""

    def test_no_args_shows_help(self) -> None:
        """Running accounts with no args shows help (exit code 2 is expected)."""
        result = runner.invoke(app, [])

        # no_args_is_help causes exit code 2
        assert result.exit_code == 2
        # Strip ANSI codes for comparison
        output = result.stdout.replace("\x1b[1m", "").replace("\x1b[0m", "")
        assert "Account management" in output
        assert "list" in output
        assert "refresh" in output

    def test_invalid_command_shows_error(self) -> None:
        """Invalid command shows error."""
        result = runner.invoke(app, ["invalid"])

        assert result.exit_code != 0
