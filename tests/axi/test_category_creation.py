"""Category creation uses the actual SDK response root and confirms its target."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


def test_category_creation_uses_real_sdk_root_and_month_default():
    from monarchmoney import MonarchMoney

    client = MonarchMoney(token="synthetic")

    async def gql_call(**kwargs):
        assert kwargs["operation"] == "Web_CreateCategory"
        values = kwargs["variables"]["input"]
        assert values["rolloverStartMonth"].endswith("-01")
        return {
            "createCategory": {
                "errors": [],
                "category": {"id": "c1", "name": values["name"], "group": {"id": values["group"]}},
            }
        }

    client.gql_call = gql_call
    with patch("monarch_cli.commands.categories.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["categories", "create", "--group", "g1", "--name", "New", "--json"]
        )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["id"] == "c1"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"errors": [{"message": "SECRET backend"}]},
        {"category": {"id": "c1", "name": "Wrong", "group": {"id": "g1"}}},
        {"category": {"id": "c1", "name": "New", "group": {"id": "other"}}},
    ],
)
def test_category_unconfirmed_creation_fails(payload):
    client = AsyncMock()
    client.create_transaction_category.return_value = {"createCategory": payload}
    with patch("monarch_cli.commands.categories.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["categories", "create", "--group", "g1", "--name", "New", "--json"]
        )
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    client.create_transaction_category.assert_awaited_once()


@pytest.mark.parametrize("extra", [["--name", ""], ["--group", ""], ["--rollover-start", "bad"]])
def test_invalid_category_input_fails_before_auth(extra):
    with patch("monarch_cli.commands.categories.get_authenticated_client") as auth:
        result = CliRunner().invoke(
            app, ["categories", "create", "--group", "g1", "--name", "New", *extra, "--json"]
        )
    assert result.exit_code == 2
    auth.assert_not_called()


@pytest.mark.parametrize("rows", [[], [{"id": "c1", "name": "Same"}, {"id": "c2", "name": "Same"}]])
def test_unknown_or_ambiguous_transaction_category_is_usage_error(rows):
    client = AsyncMock()
    client.get_transaction_categories.return_value = {"categories": rows}
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["transactions", "update", "123", "--category", "Same", "--json"]
        )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["help"] == ["monarch categories list"]
    client.update_transaction.assert_not_called()


def test_transaction_category_is_resolved_once():
    client = AsyncMock()
    client.get_transaction_categories.return_value = {
        "categories": [{"id": "c1", "name": "Selected"}]
    }
    client.get_transaction_details.return_value = {
        "getTransaction": {"id": "123", "amount": 12, "category": {"id": "old"}}
    }
    client.update_transaction.return_value = {
        "updateTransaction": {
            "errors": [],
            "transaction": {"id": "123", "amount": 12, "category": {"id": "c1"}},
        }
    }
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["transactions", "update", "123", "--category", "Selected", "--json"]
        )
    assert result.exit_code == 0, result.stdout
    client.get_transaction_categories.assert_awaited_once()
