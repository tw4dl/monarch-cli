"""Batch errors remain structured, private, and visibly unsuccessful."""

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from monarch_cli.main import app


def test_batch_failure_is_nonzero_and_does_not_leak_dependency_text():
    async def update(**kwargs):
        if kwargs["transaction_id"] == "bad":
            raise RuntimeError("SECRET dependency traceback")
        return {}, {}

    with (
        patch("monarch_cli.commands.transactions.get_authenticated_client"),
        patch("monarch_cli.commands.transactions._update_transaction_safely", side_effect=update),
    ):
        result = CliRunner().invoke(
            app, ["transactions", "batch-update", "ok", "bad", "--notes", "new", "--json"]
        )
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    data = json.loads(result.stdout)
    assert data["success_count"] == data["failure_count"] == 1
    assert data["failures"][0]["help"] == "monarch transactions show bad"


def test_batch_noop_is_acknowledged_as_success():
    with (
        patch("monarch_cli.commands.transactions.get_authenticated_client"),
        patch(
            "monarch_cli.commands.transactions._update_transaction_safely",
            new=AsyncMock(return_value=({"status": "unchanged"}, {})),
        ) as update,
    ):
        result = CliRunner().invoke(
            app, ["transactions", "batch-update", "123", "--notes", "same", "--json"]
        )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["success_count"] == 1
    assert data["results"] == [{"id": "123", "status": "unchanged"}]
    update.assert_awaited_once()
