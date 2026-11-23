"""Nested SDK collections retain honest totals, compact rows, and legacy JSON."""

import copy
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app

runner = CliRunner()


def invoke(group, method, payload, words, flags=()):
    client = MagicMock()
    setattr(client, method, AsyncMock(return_value=copy.deepcopy(payload)))
    with patch(f"monarch_cli.commands.{group}.get_authenticated_client", return_value=client):
        return runner.invoke(app, [group, *words, *flags])


def cashflow():
    def rows(kind):
        return [
            {
                "groupBy": {kind: {"id": str(i), "name": "Shop", "logoUrl": "NOISY_URL"}},
                "summary": {"sum": -5, "sumIncome": 0, "sumExpense": -5},
                "__typename": "NOISY_TYPE",
            }
            for i in range(4)
        ]

    return {
        "byCategory": rows("category"),
        "byCategoryGroup": rows("categoryGroup"),
        "byMerchant": rows("merchant"),
        "summary": [
            {"summary": {"sumIncome": 100, "sumExpense": -20, "savings": 80, "savingsRate": 0.8}}
        ],
    }


def test_cashflow_aggregates_have_total_counts_and_actual_client_limit():
    result = invoke(
        "cashflow", "get_cashflow", cashflow(), ["detail", "--limit", "2", "--preset", "this-month"]
    )
    assert result.exit_code == 0, result.output
    assert "byCategory:" in result.stdout
    assert result.stdout.count("count: 2\n") >= 3
    assert result.stdout.count("total_count: 4") >= 3
    assert "NOISY_URL" not in result.stdout and "NOISY_TYPE" not in result.stdout
    assert "--limit 4" in result.stdout and "--preset this-month" in result.stdout


@pytest.mark.parametrize("flags", [["--json"], ["--format", "json"]])
def test_cashflow_explicit_json_keeps_exact_complete_schema(flags):
    payload = cashflow()
    result = invoke("cashflow", "get_cashflow", payload, ["detail", "--limit", "2"], flags)
    assert result.exit_code == 0
    assert json.loads(result.stdout) == payload


def test_nested_empty_results_are_explicit_success():
    payload = {"byCategory": [], "byCategoryGroup": [], "byMerchant": [], "summary": []}
    result = invoke("cashflow", "get_cashflow", payload, ["detail"])
    assert result.exit_code == 0, result.output
    assert result.stdout.count("total_count: 0") == 4
    assert "No cashflow detail byCategory results" in result.stdout


def history():
    return {
        "account": {"id": "123", "displayName": "Cash", "__typename": "Account"},
        "snapshots": [
            {"date": "2026-01-01", "signedBalance": 10},
            {"date": "2026-01-02", "signedBalance": 20},
        ],
        "transactions": {
            "totalCount": 55,
            "results": [
                {"id": "t1", "date": "2026-01-01", "amount": -1},
                {"id": "t2", "date": "2026-01-02", "amount": -2},
            ],
        },
    }


def test_history_preserves_backend_transaction_total_and_cross_command_pagination():
    result = invoke("accounts", "get_account_history", history(), ["history", "123"])
    assert result.exit_code == 0, result.output
    assert "total_count: 55" in result.stdout
    assert "monarch transactions list --account 123 --offset 2 --limit 100" in result.stdout
    assert "total_count: 2" in result.stdout


def test_nested_field_selection_uses_original_paths_and_lists():
    result = invoke(
        "accounts",
        "get_account_history",
        history(),
        ["history", "123", "--fields", "snapshots.date"],
    )
    assert result.exit_code == 0, result.output
    assert "2026-01-01" in result.stdout and "2026-01-02" in result.stdout
    assert "signedBalance" not in result.stdout
    assert "total_count: 2" in result.stdout


def test_detail_nested_rows_keep_text_preview_and_have_full_escape_hatch():
    payload = {
        "getTransaction": {
            "id": "123",
            "splitTransactions": [{"id": str(i), "notes": "X" * 1200} for i in range(101)],
        }
    }
    result = invoke("transactions", "get_transaction_details", payload, ["show", "123"])
    assert result.exit_code == 0, result.output
    assert "count: 100" in result.stdout and "total_count: 101" in result.stdout
    assert "truncated, 1200 chars total" in result.stdout
    assert "monarch transactions show 123" in result.stdout and "--full" in result.stdout
    complete = invoke("transactions", "get_transaction_details", payload, ["show", "123", "--full"])
    assert complete.exit_code == 0
    assert "count: 101" in complete.stdout
    assert "truncated," not in complete.stdout


def test_cashflow_full_keeps_additional_record_fields():
    result = invoke("cashflow", "get_cashflow", cashflow(), ["detail", "--full"])
    assert result.exit_code == 0
    assert "NOISY_URL" in result.stdout and "NOISY_TYPE" in result.stdout


def test_unpaged_top_level_list_preview_has_honest_total_and_full_hint():
    payload = {"accounts": [{"id": str(i), "recentBalances": [1, 2, 3]} for i in range(105)]}
    result = invoke("accounts", "get_recent_account_balances", payload, ["recent-balances"])
    assert result.exit_code == 0, result.output
    assert "count: 100" in result.stdout and "total_count: 105" in result.stdout
    assert "monarch accounts recent-balances" in result.stdout and "--full" in result.stdout


@pytest.mark.parametrize(
    "group,method,words",
    [
        ("cashflow", "get_cashflow", ["detail"]),
        ("accounts", "get_account_history", ["history", "123"]),
        ("accounts", "get_recent_account_balances", ["recent-balances"]),
    ],
)
def test_missing_collection_fields_are_errors_not_fake_empty_success(group, method, words):
    result = invoke(group, method, {}, words)
    assert result.exit_code == 1, result.output
    assert "error: true" in result.stdout


def test_receipt_inbox_default_covers_100_rows():
    client = MagicMock(
        gql_call=AsyncMock(return_value={"retailSyncsWithTotal": {"totalCount": 0, "results": []}})
    )
    with patch("monarch_cli.commands.receipts.get_authenticated_client", return_value=client):
        result = runner.invoke(app, ["receipts", "inbox"])
    assert result.exit_code == 0, result.output
    assert client.gql_call.await_args.kwargs["variables"]["limit"] == 100


def test_security_search_default_is_100_and_total_unavailability_is_explicit():
    client = MagicMock(
        gql_call=AsyncMock(
            return_value={
                "securities": [{"id": "s1", "ticker": "VTI", "name": "Fund", "currentPrice": 100}]
            }
        )
    )
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        result = runner.invoke(app, ["investments", "securities", "VTI"])
    assert result.exit_code == 0, result.output
    assert client.gql_call.await_args.args[2]["limit"] == 100
    assert "total_count: null" in result.stdout
    assert "total_count_available: false" in result.stdout
    assert "Total matching count was not provided by this response." in result.stdout
