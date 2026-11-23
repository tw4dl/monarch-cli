"""A transaction setter must confirm its target and every requested value."""

from unittest.mock import AsyncMock

import pytest

from monarch_cli.commands.transactions import _update_transaction_safely
from monarch_cli.core.exceptions import APIError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        None,
        {"success": True},
        {"updateTransaction": {"errors": [{"message": "SECRET"}]}},
        {"updateTransaction": {"transaction": {"id": "other", "amount": 12, "notes": "new"}}},
        {"updateTransaction": {"transaction": {"id": "123", "amount": 12, "notes": "old"}}},
    ],
)
async def test_transaction_unconfirmed_result_is_error(result):
    client = AsyncMock()
    client.get_transaction_details.return_value = {
        "getTransaction": {"id": "123", "amount": 12, "notes": "old"}
    }
    client.update_transaction.return_value = result
    with pytest.raises(APIError, match="confirm"):
        await _update_transaction_safely(
            client=client, transaction_id="123", changes={"notes": "new"}
        )
    client.update_transaction.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "before",
    [
        {},
        {"getTransaction": None},
        {"errors": ["SECRET"], "getTransaction": {"id": "123", "amount": 12}},
        {"getTransaction": {"id": "other", "amount": 12}},
        {"getTransaction": {"id": "123", "amount": True}},
    ],
)
async def test_invalid_before_state_never_writes(before):
    client = AsyncMock()
    client.get_transaction_details.return_value = before
    with pytest.raises(APIError):
        await _update_transaction_safely(
            client=client, transaction_id="123", changes={"amount": 15}
        )
    client.update_transaction.assert_not_called()
    client.gql_call.assert_not_called()


@pytest.mark.parametrize(
    "flags",
    [
        ["--amount", "nan"],
        ["--amount", "inf"],
        ["--date", "bad"],
        ["--description", ""],
        ["--category", ""],
    ],
)
def test_bad_transaction_input_fails_before_auth(flags):
    from unittest.mock import patch

    from typer.testing import CliRunner

    from monarch_cli.main import app

    with patch("monarch_cli.commands.transactions.get_authenticated_client") as auth:
        result = CliRunner().invoke(app, ["transactions", "update", "123", *flags, "--json"])
    assert result.exit_code == 2
    auth.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [0, 5])
async def test_confirmation_uses_real_sdk_operation_fields(amount):
    from graphql import print_ast
    from monarchmoney import MonarchMoney

    client = MonarchMoney(token="synthetic")
    state = {"id": "123", "amount": 12, "notes": "old"}
    mutations = []

    async def gql_call(**kwargs):
        if kwargs["operation"] == "GetTransactionDrawer":
            return {"getTransaction": dict(state)}
        assert kwargs["operation"] == "Web_TransactionDrawerUpdateTransaction"
        document = kwargs["graphql_query"]
        source = print_ast(getattr(document, "document", document))
        assert "notes" in source and "needsReview" in source and "goal" in source
        values = kwargs["variables"]["input"]
        assert values["amount"] == amount
        assert values["name"] == "Store"
        assert values["goalId"] == ""
        mutations.append(values)
        state.update(
            amount=amount,
            notes="",
            merchant={"name": "Store"},
            goal=None,
            needsReview=False,
            hideFromReports=False,
        )
        return {"updateTransaction": {"errors": None, "transaction": dict(state)}}

    client.gql_call = gql_call
    await _update_transaction_safely(
        client=client,
        transaction_id="123",
        changes={
            "amount": amount,
            "notes": "",
            "merchant_name": "Store",
            "goal_id": "",
            "needs_review": False,
            "hide_from_reports": False,
        },
    )
    assert len(mutations) == 1


@pytest.mark.asyncio
async def test_metadata_amount_readback_must_identify_same_transaction():
    client = AsyncMock()
    client.get_transaction_details.side_effect = [
        {"getTransaction": {"id": "123", "amount": 12, "notes": "old"}},
        {"getTransaction": {"id": "other", "amount": 12}},
    ]
    client.update_transaction.return_value = {
        "updateTransaction": {
            "errors": [],
            "transaction": {"id": "123", "amount": 12, "notes": "new"},
        }
    }
    with pytest.raises(APIError):
        await _update_transaction_safely(
            client=client, transaction_id="123", changes={"notes": "new"}
        )
    client.update_transaction.assert_awaited_once()
