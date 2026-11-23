"""Split setters validate totals, normalize fields, and verify desired state."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


def invoke(client, splits):
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        return CliRunner().invoke(
            app,
            [
                "transactions",
                "splits",
                "update",
                "123",
                "--splits-json",
                json.dumps(splits),
                "--json",
            ],
        )


def client_with_splits(rows=None):
    client = AsyncMock()
    client.get_transaction_splits.return_value = {
        "getTransaction": {"id": "123", "amount": 10, "splitTransactions": rows or []}
    }
    return client


def test_split_aliases_are_normalized_and_repeated_state_writes_once():
    client = client_with_splits()

    async def write(**kwargs):
        assert kwargs["split_data"] == [
            {"amount": 10, "categoryId": "c1", "merchantName": "Store", "notes": "new"}
        ]
        rows = [
            {
                "id": "s1",
                "amount": 10,
                "category": {"id": "c1"},
                "merchant": {"name": "Store"},
                "notes": "new",
            }
        ]
        client.get_transaction_splits.return_value["getTransaction"]["splitTransactions"] = rows
        return {
            "updateTransactionSplit": {
                "errors": [],
                "transaction": {
                    "id": "123",
                    "hasSplitTransactions": True,
                    "splitTransactions": rows,
                },
            }
        }

    client.update_transaction_splits.side_effect = write
    splits = [{"amount": 10, "category_id": "c1", "merchant_name": "Store", "notes": "new"}]
    first, second = invoke(client, splits), invoke(client, splits)
    assert first.exit_code == second.exit_code == 0, first.stdout + second.stdout
    assert json.loads(first.stdout)["status"] == "updated"
    assert json.loads(second.stdout)["status"] == "unchanged"
    assert json.loads(first.stdout)["split_data"] == splits
    client.update_transaction_splits.assert_awaited_once()


@pytest.mark.parametrize(
    "splits",
    [
        [{}],
        [{"amount": True, "categoryId": "c"}],
        [{"amount": float("nan"), "categoryId": "c"}],
        [{"amount": 10, "categoryId": ""}],
        [{"amount": 10, "categoryId": "c", "category_id": "other"}],
        [{"amount": 10, "categoryId": "c", "unknown": 1}],
    ],
)
def test_bad_split_fields_fail_before_auth(splits):
    with patch("monarch_cli.commands.transactions.get_authenticated_client") as auth:
        result = CliRunner().invoke(
            app,
            [
                "transactions",
                "splits",
                "update",
                "123",
                "--splits-json",
                json.dumps(splits),
                "--json",
            ],
        )
    assert result.exit_code == 2
    auth.assert_not_called()


def test_split_total_mismatch_never_writes():
    client = client_with_splits()
    result = invoke(client, [{"amount": 9, "category_id": "c1"}])
    assert result.exit_code == 2
    client.update_transaction_splits.assert_not_called()


def test_clearing_already_empty_splits_is_success_without_write():
    client = client_with_splits()
    result = invoke(client, [])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["status"] == "unchanged"
    client.update_transaction_splits.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"errors": [{"message": "SECRET backend"}]},
        {"transaction": {"id": "wrong", "splitTransactions": []}},
    ],
)
def test_unconfirmed_split_result_is_error(payload):
    client = client_with_splits()
    client.update_transaction_splits.return_value = {"updateTransactionSplit": payload}
    result = invoke(client, [{"amount": 10, "categoryId": "c1"}])
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    assert json.loads(result.stdout)["help"] == ["monarch transactions splits show 123"]
    client.update_transaction_splits.assert_awaited_once()


def test_clearing_splits_writes_once_then_acknowledges_absence():
    rows = [
        {
            "id": "s1",
            "amount": 10,
            "category": {"id": "c1"},
            "merchant": {"name": "Store"},
            "notes": None,
        }
    ]
    client = client_with_splits(rows)

    async def clear(**_kwargs):
        client.get_transaction_splits.return_value["getTransaction"]["splitTransactions"] = []
        return {
            "updateTransactionSplit": {
                "errors": None,
                "transaction": {
                    "id": "123",
                    "hasSplitTransactions": False,
                    "splitTransactions": [],
                },
            }
        }

    client.update_transaction_splits.side_effect = clear
    first, second = invoke(client, []), invoke(client, [])
    assert first.exit_code == second.exit_code == 0
    assert json.loads(second.stdout)["status"] == "unchanged"
    client.update_transaction_splits.assert_awaited_once()


def test_split_matching_preserves_duplicates_and_handles_overlapping_optional_fields():
    from monarch_cli.core.split_state import matches_splits

    rows = [
        {"amount": 5, "category": {"id": "c1"}, "merchant": {"name": "X"}, "notes": "Y"},
        {"amount": 5, "category": {"id": "c1"}, "merchant": {"name": "X"}, "notes": "Z"},
    ]
    desired = [
        {"amount": 5, "categoryId": "c1", "merchantName": "X"},
        {"amount": 5, "categoryId": "c1", "notes": "Y"},
    ]
    assert matches_splits(rows, desired)
    assert not matches_splits(rows, [desired[1], desired[1]])


def test_changed_parent_amount_fails_readback():
    rows = [
        {
            "id": "s1",
            "amount": 10,
            "category": {"id": "c1"},
            "merchant": {"name": "Store"},
            "notes": "",
        }
    ]
    client = client_with_splits()
    client.get_transaction_splits.side_effect = [
        client.get_transaction_splits.return_value,
        {"getTransaction": {"id": "123", "amount": 11, "splitTransactions": rows}},
    ]
    client.update_transaction_splits.return_value = {
        "updateTransactionSplit": {
            "errors": [],
            "transaction": {"id": "123", "hasSplitTransactions": True, "splitTransactions": rows},
        }
    }
    result = invoke(client, [{"amount": 10, "categoryId": "c1"}])
    assert result.exit_code == 1
    client.update_transaction_splits.assert_awaited_once()


def test_split_fields_reach_real_sdk_mutation():
    from graphql import print_ast
    from monarchmoney import MonarchMoney

    client = MonarchMoney(token="synthetic")
    state = {"rows": []}

    async def gql_call(**kwargs):
        document = kwargs["graphql_query"]
        source = print_ast(getattr(document, "document", document))
        if kwargs["operation"] == "TransactionSplitQuery":
            assert "getTransaction" in source
            return {
                "getTransaction": {"id": "123", "amount": 10, "splitTransactions": state["rows"]}
            }
        assert kwargs["operation"] == "Common_SplitTransactionMutation"
        assert "updateTransactionSplit" in source
        assert kwargs["variables"]["input"] == {
            "transactionId": "123",
            "splitData": [{"amount": 10, "categoryId": "c1"}],
        }
        state["rows"] = [
            {
                "id": "s1",
                "amount": 10,
                "category": {"id": "c1"},
                "merchant": {"name": "Store"},
                "notes": "",
            }
        ]
        return {
            "updateTransactionSplit": {
                "errors": [],
                "transaction": {
                    "id": "123",
                    "hasSplitTransactions": True,
                    "splitTransactions": state["rows"],
                },
            }
        }

    client.gql_call = gql_call
    result = invoke(client, [{"amount": 10, "category_id": "c1"}])
    assert result.exit_code == 0, result.stdout
