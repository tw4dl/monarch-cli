"""Balance history uploads validate local input and require literal completion."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize("completion", [False, None, 1, "true", {"status": "completed"}, True])
def test_history_upload_requires_literal_true(tmp_path, completion):
    history = tmp_path / "history.csv"
    history.write_text("date,amount\n2026-11-01,12.50\n")
    client = AsyncMock()
    client.upload_account_balance_history.return_value = completion
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["accounts", "upload-history", "123", str(history), "--json"]
        )
    assert result.exit_code == (0 if completion is True else 1)
    if completion is True:
        assert json.loads(result.stdout)["status"] == "uploaded"
    client.upload_account_balance_history.assert_awaited_once()


@pytest.mark.parametrize(
    "content",
    [
        "",
        "date,amount\n",
        "date,amount\nbad,12\n",
        "date,amount\n2026-11-01,nan\n",
        "date,amount\n2026-11-01,inf\n",
        "date,amount\n2026-11-01,12,extra\n",
        "date,amount,amount\n2026-11-01,12,13\n",
        "date,balance,amount\n2026-11-01,12,13\n",
        "date,amount\n2026-11-01,12\n2026-11-01,13\n",
    ],
)
def test_invalid_history_never_loads_auth(tmp_path, content):
    history = tmp_path / "history.csv"
    history.write_text(content)
    with patch("monarch_cli.commands.accounts.get_authenticated_client") as auth:
        result = CliRunner().invoke(
            app, ["accounts", "upload-history", "123", str(history), "--json"]
        )
    assert result.exit_code == 2, result.stdout
    auth.assert_not_called()


@pytest.mark.parametrize("flag", ["--timeout", "--delay"])
def test_history_polling_requires_positive_values(tmp_path, flag):
    history = tmp_path / "history.csv"
    history.write_text("date,amount\n2026-11-01,12.50\n")
    with patch("monarch_cli.commands.accounts.get_authenticated_client") as auth:
        result = CliRunner().invoke(
            app, ["accounts", "upload-history", "123", str(history), flag, "0", "--json"]
        )
    assert result.exit_code == 2
    auth.assert_not_called()


def test_history_balance_alias_and_bom_use_real_sdk_with_stubbed_upload(tmp_path):
    from monarchmoney import MonarchMoney

    history = tmp_path / "history.csv"
    history.write_text("\ufeffDate,Balance,Account Name\n2026-11-01,-12.50,Manual\n")
    client = MonarchMoney(token="synthetic")
    client._upload_form_data = AsyncMock(return_value={"session_key": "synthetic"})
    client._initiate_upload_balance_history_session = AsyncMock(
        return_value={
            "parseBalanceHistory": {"uploadBalanceHistorySession": {"status": "completed"}}
        }
    )
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app, ["accounts", "upload-history", "123", str(history), "--json"]
        )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["result"] is True
    client._upload_form_data.assert_awaited_once()
    client._initiate_upload_balance_history_session.assert_awaited_once_with(
        session_key="synthetic"
    )
