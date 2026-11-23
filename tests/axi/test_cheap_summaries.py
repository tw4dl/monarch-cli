"""Already-fetched related state belongs in compact agent list rows."""

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from monarch_cli.main import app


def test_receipt_inbox_inlines_merchant_and_verified_link_counts():
    receipt = {
        "id": "r1",
        "status": "pending_matches",
        "vendor": "user_import",
        "createdAt": "2026-11-01",
        "orders": [
            {
                "merchantName": "Store",
                "retailTransactions": [
                    {"id": "one", "transaction": None},
                    {"id": "two", "transaction": {"id": "t2"}},
                ],
            }
        ],
    }
    client = AsyncMock()
    client.gql_call.return_value = {"retailSyncsWithTotal": {"totalCount": 1, "results": [receipt]}}
    with patch("monarch_cli.commands.receipts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["receipts", "inbox"])
        legacy = CliRunner().invoke(app, ["receipts", "inbox", "--json"])
    assert result.exit_code == 0, result.stdout
    assert "{id,status,merchant,matches}" in result.stdout
    assert "r1,pending_matches,Store,1/2" in result.stdout
    assert json.loads(legacy.stdout)["results"] == [receipt]


def test_missing_receipt_link_data_is_unknown_not_zero():
    client = AsyncMock()
    client.gql_call.return_value = {
        "retailSyncsWithTotal": {
            "totalCount": 1,
            "results": [{"id": "r1", "status": "pending_matches", "vendor": "user_import"}],
        }
    }
    with patch("monarch_cli.commands.receipts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["receipts", "inbox"])
    assert result.exit_code == 0
    assert "{id,status,merchant,matches}" in result.stdout
    assert "0/0" not in result.stdout


def test_tag_list_inlines_backend_count_and_discloses_tagged_transactions():
    tag = {"id": "t1", "name": "Tax", "color": "#2f855a", "transactionCount": 7, "order": 1}
    client = AsyncMock()
    client.get_transaction_tags.return_value = {"householdTransactionTags": [tag]}
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["transactions", "tags", "list"])
        legacy = CliRunner().invoke(app, ["transactions", "tags", "list", "--json"])
    assert result.exit_code == 0
    assert "{id,name,color,transactionCount}" in result.stdout
    assert "monarch transactions list --tag t1" in result.stdout
    assert json.loads(legacy.stdout) == {"householdTransactionTags": [tag]}
