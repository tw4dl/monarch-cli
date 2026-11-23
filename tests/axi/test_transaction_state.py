"""Desired transaction state is acknowledged without a duplicate write."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "flags,fields",
    [
        (["--notes", ""], {"notes": ""}),
        (["--notes", ""], {"notes": None}),
        (["--amount", "0"], {"amount": 0}),
        (["--description", "Store"], {"merchant": {"name": "Store"}}),
        (["--date", "2026-11-01"], {"date": "2026-11-01"}),
        (["--goal", ""], {"goal": None}),
        (["--hide-from-reports"], {"hideFromReports": True}),
        (["--clear-review"], {"needsReview": False}),
    ],
)
def test_matching_transaction_state_is_unchanged(flags, fields):
    client = AsyncMock()
    client.get_transaction_details.return_value = {
        "getTransaction": {"id": "123", "amount": 12, **fields}
    }
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["transactions", "update", "123", *flags, "--json"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["status"] == "unchanged"
    client.update_transaction.assert_not_called()
    client.gql_call.assert_not_called()


def test_missing_current_field_does_not_prove_matching_state():
    client = AsyncMock()
    client.get_transaction_details.return_value = {"getTransaction": {"id": "123", "amount": 12}}
    client.update_transaction.return_value = {
        "updateTransaction": {"transaction": {"id": "123", "amount": 12, "notes": ""}, "errors": []}
    }
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["transactions", "update", "123", "--notes", "", "--json"])
    assert result.exit_code == 0, result.stdout
    client.update_transaction.assert_awaited_once()


def test_repeated_multi_field_update_writes_once():
    state = {"id": "123", "amount": 12, "notes": "old", "needsReview": True}
    client = AsyncMock()

    async def read(**_kwargs):
        return {"getTransaction": dict(state)}

    async def write(**kwargs):
        state.update(
            amount=kwargs["amount"], notes=kwargs["notes"], needsReview=kwargs["needs_review"]
        )
        return {"updateTransaction": {"errors": [], "transaction": dict(state)}}

    client.get_transaction_details.side_effect = read
    client.update_transaction.side_effect = write
    words = [
        "transactions",
        "update",
        "123",
        "--amount",
        "15",
        "--notes",
        "new",
        "--clear-review",
        "--json",
    ]
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        first = CliRunner().invoke(app, words)
        second = CliRunner().invoke(app, words)
    assert first.exit_code == second.exit_code == 0
    assert json.loads(first.stdout)["status"] == "updated"
    assert json.loads(second.stdout)["status"] == "unchanged"
    client.update_transaction.assert_awaited_once()
