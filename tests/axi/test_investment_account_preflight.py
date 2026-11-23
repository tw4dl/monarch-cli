"""Investment creation cannot infer absence from an incomplete account list."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app

WORDS = ["accounts", "create-investments", "--name", "Manual", "--subtype", "brokerage", "--json"]


@pytest.mark.parametrize(
    "payload",
    [{}, {"errors": ["failed"], "accounts": []}, {"accounts": [{"displayName": "Other"}]}],
)
def test_invalid_preflight_cannot_create(payload):
    client = MagicMock(get_accounts=AsyncMock(return_value=payload), gql_call=AsyncMock())
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, WORDS)
    assert result.exit_code == 1
    client.gql_call.assert_not_awaited()


@pytest.mark.parametrize("flag", ["--name", "--subtype"])
def test_blank_required_input_before_auth(flag):
    words = WORDS.copy()
    words[words.index(flag) + 1] = " "
    with patch("monarch_cli.commands.accounts.get_authenticated_client") as auth:
        result = CliRunner().invoke(app, words)
    assert result.exit_code == 2
    auth.assert_not_called()


@pytest.mark.parametrize("quantity", ["1e1000", "-1e1000", "1e-1000", "-1e-1000"])
def test_unrepresentable_holding_quantity_before_auth(quantity):
    with patch("monarch_cli.commands.accounts.get_authenticated_client") as auth:
        result = CliRunner().invoke(app, [*WORDS, "--holding", f"s1={quantity}"])
    assert result.exit_code == 2
    auth.assert_not_called()
