"""Creation and upsert must not invent success or miss later duplicate pages."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


def record(identifier="new", amount=10):
    return {
        "id": identifier,
        "date": "2026-11-01",
        "amount": amount,
        "merchant": {"name": "Store"},
        "category": {"id": "c1"},
        "account": {"id": "a1"},
        "notes": "",
        "tags": [],
    }


def client_for_creation():
    client = AsyncMock()
    client.create_transaction.return_value = {
        "createTransaction": {"errors": [], "transaction": {"id": "new"}}
    }
    client.get_transaction_details.return_value = {"getTransaction": record()}
    client.get_transactions.return_value = {"allTransactions": {"totalCount": 0, "results": []}}
    return client


def invoke(client, action="create", extra=()):
    words = [
        "transactions",
        action,
        "--date",
        "2026-11-01",
        "--account",
        "a1",
        "--amount",
        "10",
        "--merchant",
        "Store",
        "--category",
        "c1",
        *extra,
        "--json",
    ]
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        return CliRunner().invoke(app, words)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"errors": [{"message": "SECRET backend"}], "transaction": {"id": "new"}},
        {"transaction": {}},
    ],
)
def test_unconfirmed_transaction_creation_stops_followups(payload):
    client = client_for_creation()
    client.create_transaction.return_value = {"createTransaction": payload}
    result = invoke(client, extra=["--tag", "t1"])
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    client.set_transaction_tags.assert_not_called()


def test_tag_assignment_must_be_confirmed_before_created_success():
    client = client_for_creation()
    client.set_transaction_tags.return_value = {
        "setTransactionTags": {"errors": [{"message": "SECRET backend"}]}
    }
    result = invoke(client, extra=["--tag", "t1"])
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    client.create_transaction.assert_awaited_once()
    client.set_transaction_tags.assert_awaited_once()


def test_already_applied_creation_tags_need_no_write():
    client = client_for_creation()
    client.get_transaction_details.return_value["getTransaction"]["tags"] = [{"id": "t1"}]
    result = invoke(client, extra=["--tag", "t1"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["tag_ids"] == ["t1"]
    client.set_transaction_tags.assert_not_called()


def test_upsert_searches_later_pages_before_creating():
    client = client_for_creation()
    client.get_transactions.side_effect = [
        {"allTransactions": {"totalCount": 2, "results": [record("other", 5)]}},
        {"allTransactions": {"totalCount": 2, "results": [record("existing", 10)]}},
    ]
    result = invoke(client, action="upsert")
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["id"] == "existing"
    assert [call.kwargs["offset"] for call in client.get_transactions.await_args_list] == [0, 1]
    client.create_transaction.assert_not_called()


@pytest.mark.parametrize(
    "page",
    [
        {},
        {"allTransactions": {"results": []}},
        {"allTransactions": {"totalCount": 1, "results": []}},
        {"allTransactions": {"totalCount": 1, "results": [record(amount=None)]}},
    ],
)
def test_incomplete_upsert_search_cannot_establish_absence(page):
    client = client_for_creation()
    client.get_transactions.return_value = page
    result = invoke(client, action="upsert")
    assert result.exit_code == 1
    client.create_transaction.assert_not_called()


@pytest.mark.parametrize(
    "extra",
    [
        ["--amount", "nan"],
        ["--date", "bad"],
        ["--merchant", ""],
        ["--account", ""],
        ["--tag", ""],
    ],
)
def test_bad_creation_input_fails_before_auth(extra):
    with patch("monarch_cli.commands.transactions.get_authenticated_client") as auth:
        words = [
            "transactions",
            "create",
            "--date",
            "2026-11-01",
            "--account",
            "a1",
            "--amount",
            "10",
            "--merchant",
            "Store",
            "--category",
            "c1",
            *extra,
            "--json",
        ]
        result = CliRunner().invoke(app, words)
    assert result.exit_code == 2
    auth.assert_not_called()


@pytest.mark.parametrize(
    "changes", [{"amount": 99}, {"account": {"id": "other"}}, {"merchant": {"name": "Wrong"}}]
)
def test_contradicting_creation_readback_is_error(changes):
    client = client_for_creation()
    client.get_transaction_details.return_value["getTransaction"].update(changes)
    result = invoke(client)
    assert result.exit_code == 1
    client.create_transaction.assert_awaited_once()


def test_tag_readback_must_still_match_after_creation():
    client = client_for_creation()
    client.set_transaction_tags.return_value = {
        "setTransactionTags": {"errors": [], "transaction": {"id": "new", "tags": [{"id": "t1"}]}}
    }
    result = invoke(client, extra=["--tag", "t1"])
    assert result.exit_code == 1
    client.create_transaction.assert_awaited_once()


@pytest.mark.parametrize(
    "second",
    [
        {"totalCount": 2, "results": [record("one", 5)]},
        {"totalCount": 3, "results": [record("two", 5)]},
    ],
)
def test_inconsistent_candidate_pagination_never_creates(second):
    client = client_for_creation()
    client.get_transactions.side_effect = [
        {"allTransactions": {"totalCount": 2, "results": [record("one", 5)]}},
        {"allTransactions": second},
    ]
    result = invoke(client, action="upsert")
    assert result.exit_code == 1
    client.create_transaction.assert_not_called()


def test_excluding_category_from_dedupe_does_not_filter_it_out():
    client = client_for_creation()
    existing = record("existing")
    existing["category"]["id"] = "other"
    client.get_transactions.return_value = {
        "allTransactions": {"totalCount": 1, "results": [existing]}
    }
    result = invoke(client, action="upsert", extra=["--dedupe-key", "date,amount,notes"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["id"] == "existing"
    assert client.get_transactions.call_args.kwargs["category_ids"] == []
    client.create_transaction.assert_not_called()


def test_create_preserves_sdk_cent_rounding_contract():
    client = client_for_creation()
    client.get_transaction_details.return_value["getTransaction"]["amount"] = 10.12
    result = invoke(client, extra=["--amount", "10.125"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["amount"] == 10.12


@pytest.mark.parametrize("amount", [0, 10])
def test_create_then_upsert_and_tags_use_real_sdk_once(amount):
    from graphql import print_ast
    from monarchmoney import MonarchMoney

    client = MonarchMoney(token="synthetic")
    state = {"transaction": None}
    mutations = []

    async def gql_call(**kwargs):
        operation = kwargs["operation"]
        if operation == "Common_CreateTransactionMutation":
            values = kwargs["variables"]["input"]
            assert values["amount"] == amount and values["accountId"] == "a1"
            state["transaction"] = record(amount=amount)
            mutations.append(operation)
            return {"createTransaction": {"errors": None, "transaction": {"id": "new"}}}
        if operation == "Web_SetTransactionTags":
            assert kwargs["variables"]["input"] == {"transactionId": "new", "tagIds": ["t1"]}
            state["transaction"]["tags"] = [{"id": "t1"}]
            mutations.append(operation)
            return {"setTransactionTags": {"errors": [], "transaction": state["transaction"]}}
        if operation == "GetTransactionDrawer":
            assert kwargs["variables"] == {"id": "new", "redirectPosted": False}
            return {"getTransaction": state["transaction"]}
        document = kwargs["graphql_query"]
        assert "totalCount" in print_ast(getattr(document, "document", document))
        return {
            "allTransactions": {
                "totalCount": 1 if state["transaction"] else 0,
                "results": [state["transaction"]] if state["transaction"] else [],
            }
        }

    client.gql_call = gql_call
    extra = ["--amount", str(amount), "--tag", "t1"]
    first = invoke(client, action="upsert", extra=extra)
    second = invoke(client, action="upsert", extra=extra)
    assert first.exit_code == second.exit_code == 0, first.stdout + second.stdout
    assert json.loads(first.stdout)["status"] == "created"
    assert json.loads(second.stdout)["status"] == "existing"
    assert mutations == ["Common_CreateTransactionMutation", "Web_SetTransactionTags"]
