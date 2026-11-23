"""Account setters acknowledge matching state and require confirmed fields."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


def invoke(client, flags):
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        return CliRunner().invoke(app, ["accounts", "update", "123", *flags, "--json"])


def test_repeated_account_update_writes_once_with_real_sdk():
    from monarchmoney import MonarchMoney

    client = MonarchMoney(token="synthetic")
    state = {"id": "123", "displayName": "Old", "displayBalance": 15}
    writes = []

    async def gql_call(**kwargs):
        if kwargs["operation"] != "Common_UpdateAccount":
            return {"accounts": [dict(state)]}
        values = kwargs["variables"]["input"]
        writes.append(values)
        state.update(
            displayName=values["name"],
            displayBalance=values["displayBalance"],
            includeInNetWorth=values["includeInNetWorth"],
            hideFromList=values["hideFromList"],
        )
        return {"updateAccount": {"errors": None, "account": dict(state)}}

    client.gql_call = gql_call
    flags = ["--name", "New", "--balance", "0", "--exclude-from-net-worth", "--show-in-summary"]
    first, second = invoke(client, flags), invoke(client, flags)
    assert first.exit_code == second.exit_code == 0, first.stdout + second.stdout
    assert json.loads(first.stdout)["status"] == "updated"
    assert json.loads(second.stdout)["status"] == "unchanged"
    assert len(writes) == 1


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"errors": [{"message": "SECRET backend"}]},
        {"account": {"id": "other", "displayName": "New"}},
        {"account": {"id": "123", "displayName": "Old"}},
    ],
)
def test_account_unconfirmed_payload_fails(payload):
    client = AsyncMock()
    client.get_accounts.return_value = {"accounts": [{"id": "123", "displayName": "Old"}]}
    client.update_account.return_value = {"updateAccount": payload}
    result = invoke(client, ["--name", "New"])
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    client.update_account.assert_awaited_once()


@pytest.mark.parametrize("source", [{}, {"accounts": []}, {"accounts": [{"displayName": "New"}]}])
def test_missing_or_malformed_account_never_writes(source):
    client = AsyncMock()
    client.get_accounts.return_value = source
    result = invoke(client, ["--name", "New"])
    assert result.exit_code == 1
    client.update_account.assert_not_called()


@pytest.mark.parametrize(
    "flags", [["--balance", "nan"], ["--balance", "inf"], ["--name", ""], ["--type", ""]]
)
def test_bad_account_inputs_fail_before_auth(flags):
    with patch("monarch_cli.commands.accounts.get_authenticated_client") as auth:
        result = CliRunner().invoke(app, ["accounts", "update", "123", *flags, "--json"])
    assert result.exit_code == 2
    auth.assert_not_called()
