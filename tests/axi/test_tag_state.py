"""Tag desired-state operations preserve other tags and acknowledge no-ops."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


def client_with(tags):
    state = list(tags)

    async def read(**kwargs):
        assert kwargs == {"transaction_id": "123", "redirect_posted": False}
        return {"getTransaction": {"id": "123", "tags": [{"id": value} for value in state]}}

    async def write(transaction_id, tag_ids):
        assert transaction_id == "123"
        state[:] = tag_ids
        return {
            "setTransactionTags": {
                "errors": None,
                "transaction": {"id": "123", "tags": [{"id": value} for value in state]},
            }
        }

    return MagicMock(
        get_transaction_details=AsyncMock(side_effect=read),
        set_transaction_tags=AsyncMock(side_effect=write),
    )


@pytest.mark.parametrize(
    "action,flags,before,expected",
    [
        ("set", ["--tag", "a", "--tag", "b"], ["b", "a"], ["b", "a"]),
        ("remove", ["--tag", "missing"], ["a", "b"], ["a", "b"]),
        ("clear", [], [], []),
    ],
)
def test_existing_tag_state_is_a_successful_noop(action, flags, before, expected):
    client = client_with(before)
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["transactions", "tags", action, "123", *flags, "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["status"] == "unchanged"
    assert data["tag_ids"] == expected
    client.set_transaction_tags.assert_not_called()


@pytest.mark.parametrize(
    "action,flags,before,expected",
    [
        ("set", ["--tag", "b", "--tag", "b"], ["a"], ["b"]),
        ("remove", ["--tag", "a"], ["a", "b"], ["b"]),
        ("clear", [], ["a", "b"], []),
    ],
)
def test_tag_change_is_applied_once_and_repetition_does_not_write(action, flags, before, expected):
    client = client_with(before)
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        first = CliRunner().invoke(app, ["transactions", "tags", action, "123", *flags, "--json"])
        second = CliRunner().invoke(app, ["transactions", "tags", action, "123", *flags, "--json"])
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert json.loads(first.stdout)["tag_ids"] == expected
    assert json.loads(second.stdout)["status"] == "unchanged"
    client.set_transaction_tags.assert_awaited_once_with(transaction_id="123", tag_ids=expected)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"getTransaction": {}},
        {"getTransaction": {"id": "123"}},
        {"getTransaction": {"id": "123", "tags": [{}]}},
    ],
)
def test_incomplete_tag_read_never_clears_tags(payload):
    client = MagicMock(get_transaction_details=AsyncMock(return_value=payload))
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["transactions", "tags", "remove", "123", "--tag", "a", "--json"]
        )
    assert result.exit_code == 1
    client.set_transaction_tags.assert_not_called()


def test_unconfirmed_tag_write_is_an_error():
    client = client_with(["a"])
    client.set_transaction_tags = AsyncMock(
        return_value={
            "setTransactionTags": {
                "errors": None,
                "transaction": {"id": "123", "tags": [{"id": "a"}]},
            }
        }
    )
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["transactions", "tags", "clear", "123", "--json"])
    assert result.exit_code == 1, result.output
    client.set_transaction_tags.assert_awaited_once()


def test_empty_tag_id_fails_before_authentication():
    with patch("monarch_cli.commands.transactions.get_authenticated_client") as client:
        result = CliRunner().invoke(
            app, ["transactions", "tags", "set", "123", "--tag", "", "--json"]
        )
    assert result.exit_code == 2
    client.assert_not_called()


async def test_tag_state_uses_real_sdk_query_and_preserves_unremoved_tags():
    from graphql.language import FieldNode, OperationDefinitionNode
    from monarchmoney import MonarchMoney

    from monarch_cli.core.tag_state import change_tags

    client = MonarchMoney()

    async def response(*, operation, graphql_query, variables):
        document = getattr(graphql_query, "document", graphql_query)
        definition = next(
            node for node in document.definitions if isinstance(node, OperationDefinitionNode)
        )
        field = next(
            node for node in definition.selection_set.selections if isinstance(node, FieldNode)
        )
        name = field.alias.value if field.alias else field.name.value
        if operation == "GetTransactionDrawer":
            return {name: {"id": "123", "tags": [{"id": "a"}, {"id": "b"}]}}
        assert operation == "Web_SetTransactionTags"
        assert variables == {"input": {"transactionId": "123", "tagIds": ["b"]}}
        return {
            name: {
                "errors": None,
                "transaction": {"id": "123", "tags": [{"id": "b"}]},
            }
        }

    client.gql_call = AsyncMock(side_effect=response)
    result = await change_tags(client, "123", mode="remove", values=["a"])
    assert result["tag_ids"] == ["b"]
    assert client.gql_call.await_count == 2
