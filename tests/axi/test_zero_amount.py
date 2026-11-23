"""Zero amounts must reach GraphQL rather than being dropped by the SDK."""

from unittest.mock import AsyncMock

import pytest

from monarch_cli.commands.transactions import _update_transaction_safely
from monarch_cli.core.exceptions import APIError


@pytest.mark.asyncio
async def test_zero_amount_is_sent_and_verified():
    client = AsyncMock()
    client.get_transaction_details.return_value = {"getTransaction": {"id": "123", "amount": 5}}
    client.gql_call.return_value = {
        "updateTransaction": {"errors": [], "transaction": {"id": "123", "amount": 0}}
    }
    await _update_transaction_safely(client=client, transaction_id="123", changes={"amount": 0})
    client.update_transaction.assert_not_called()
    assert client.gql_call.call_args.kwargs["variables"]["input"] == {"id": "123", "amount": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"errors": [{"message": "private backend text"}]},
        {"transaction": {"id": "other", "amount": 0}},
        {"transaction": {"id": "123", "amount": 7}},
    ],
)
async def test_zero_amount_requires_confirmed_response(payload):
    client = AsyncMock()
    client.get_transaction_details.return_value = {"getTransaction": {"id": "123", "amount": 5}}
    client.gql_call.return_value = {"updateTransaction": payload}
    with pytest.raises(APIError, match="confirm"):
        await _update_transaction_safely(client=client, transaction_id="123", changes={"amount": 0})


@pytest.mark.asyncio
async def test_metadata_update_preserves_zero_and_empty_values():
    client = AsyncMock()
    client.get_transaction_details.return_value = {"getTransaction": {"id": "123", "amount": 0}}
    client.gql_call.return_value = {
        "updateTransaction": {
            "errors": [],
            "transaction": {
                "id": "123",
                "amount": 0,
                "notes": "",
                "goal": None,
                "needsReview": False,
                "hideFromReports": False,
            },
        }
    }
    await _update_transaction_safely(
        client=client,
        transaction_id="123",
        changes={"notes": "", "goal_id": "", "needs_review": False, "hide_from_reports": False},
    )
    assert client.gql_call.call_args.kwargs["variables"]["input"] == {
        "id": "123",
        "amount": 0,
        "notes": "",
        "goalId": "",
        "needsReview": False,
        "hideFromReports": False,
    }
    assert client.get_transaction_details.await_count == 2
