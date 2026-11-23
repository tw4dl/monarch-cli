"""Account metadata is discoverable without a balance-history request."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "flags", [["--json"], ["--fields", "id,displayName,includeInNetWorth", "--json"]]
)
def test_account_show_returns_exact_record_without_changing_list_schema(flags):
    client = AsyncMock()
    expected = {"id": "123", "displayName": "Cash", "includeInNetWorth": False}
    client.get_accounts.return_value = {
        "accounts": [{"id": "other", "displayName": "Other"}, expected]
    }
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["accounts", "show", "123", *flags])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == expected
    client.get_account_history.assert_not_called()


@pytest.mark.parametrize(
    "source", [{}, {"accounts": []}, {"accounts": [{"id": "123"}, {"id": "123"}]}]
)
def test_account_show_rejects_missing_or_malformed_source(source):
    client = AsyncMock()
    client.get_accounts.return_value = source
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["accounts", "show", "123", "--json"])
    assert result.exit_code == 1


def test_uncertain_account_update_inspects_metadata():
    client = AsyncMock()
    client.get_accounts.return_value = {"accounts": [{"id": "123", "displayName": "Old"}]}
    client.update_account.side_effect = TimeoutError()
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["accounts", "update", "123", "--name", "New", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["help"] == ["monarch accounts show 123"]


def test_uncertain_transaction_creation_keeps_account_and_day():
    client = AsyncMock()
    client.create_transaction.side_effect = TimeoutError()
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app,
            [
                "transactions",
                "create",
                "--account",
                "a1",
                "--date",
                "2026-11-01",
                "--amount",
                "10",
                "--merchant",
                "Store",
                "--category",
                "c1",
                "--json",
            ],
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["help"] == [
        "monarch transactions list --account a1 --start 2026-11-01 --end 2026-11-01"
    ]


def test_account_list_discloses_the_metadata_detail_command():
    client = AsyncMock()
    client.get_accounts.return_value = {"accounts": [{"id": "123", "displayName": "Cash"}]}
    with patch("monarch_cli.services.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["accounts", "list"])
    assert result.exit_code == 0, result.stdout
    assert "monarch accounts show 123" in result.stdout
