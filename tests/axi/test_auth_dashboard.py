"""All public auth operations are flag-complete; startup reads useful live state."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.core.exceptions import AuthenticationError
from monarch_cli.main import app

runner = CliRunner()


def test_login_missing_values_never_prompts():
    with patch("typer.prompt", side_effect=AssertionError("must not prompt")):
        result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 2
    assert "--email" in result.stdout
    assert result.stderr == ""


def test_login_uses_flags_and_does_not_print_secrets(tmp_path):
    secret = tmp_path / "password"
    secret.write_text("secret-value\n")
    client = MagicMock(token="session-secret", login=AsyncMock())
    with (
        patch("monarch_cli.commands.auth.MonarchMoney", return_value=client),
        patch("monarch_cli.commands.auth.save_session_token") as save,
    ):
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--email",
                "me@example.com",
                "--password-file",
                str(secret),
                "--storage",
                "file",
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    client.login.assert_awaited_once_with(
        "me@example.com", "secret-value", use_saved_session=False, save_session=False
    )
    save.assert_called_once()
    assert "secret-value" not in result.output and "session-secret" not in result.output
    assert json.loads(result.stdout)["status"] == "authenticated"


def test_mfa_missing_code_fails_without_prompt_or_saving(tmp_path):
    from monarchmoney import RequireMFAException

    secret = tmp_path / "password"
    secret.write_text("password")
    client = MagicMock(login=AsyncMock(side_effect=RequireMFAException))
    with (
        patch("monarch_cli.commands.auth.MonarchMoney", return_value=client),
        patch("monarch_cli.commands.auth.save_session_token") as save,
        patch("typer.prompt", side_effect=AssertionError("must not prompt")),
    ):
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--email",
                "me@example.com",
                "--password-file",
                str(secret),
                "--storage",
                "file",
                "--json",
            ],
        )
    assert result.exit_code == 2
    assert "--mfa-code" in json.loads(result.stdout)["message"]
    assert "password" not in json.loads(result.stdout).get("details", {})
    save.assert_not_called()


def test_mfa_flag_completes_login(tmp_path, monkeypatch):
    from monarchmoney import RequireMFAException

    secret = tmp_path / "password"
    secret.write_text("päss東京", encoding="utf-8")
    original_read = type(secret).read_text

    def locale_read(path, *args, **kwargs):
        if path == secret and "encoding" not in kwargs:
            kwargs["encoding"] = "cp1252"
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(type(secret), "read_text", locale_read)
    client = MagicMock(
        token="session-secret",
        login=AsyncMock(side_effect=RequireMFAException),
        multi_factor_authenticate=AsyncMock(),
    )
    with (
        patch("monarch_cli.commands.auth.MonarchMoney", return_value=client),
        patch("monarch_cli.commands.auth.save_session_token"),
    ):
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--email",
                "me@example.com",
                "--password-file",
                str(secret),
                "--mfa-code",
                "123456",
                "--storage",
                "file",
            ],
        )
    assert result.exit_code == 0, result.output
    client.multi_factor_authenticate.assert_awaited_once_with(
        "me@example.com", "päss東京", "123456"
    )
    assert "123456" not in result.output


@pytest.mark.parametrize("content", ["", "\n"])
def test_empty_password_file_rejected_before_client(tmp_path, content):
    secret = tmp_path / "password"
    secret.write_text(content)
    with patch("monarch_cli.commands.auth.MonarchMoney") as client:
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--email",
                "me@example.com",
                "--password-file",
                str(secret),
                "--storage",
                "file",
            ],
        )
    assert result.exit_code == 2
    client.assert_not_called()


def test_login_failure_does_not_echo_dependency_error(tmp_path):
    secret = tmp_path / "password"
    secret.write_text("password")
    client = MagicMock(login=AsyncMock(side_effect=RuntimeError("dependency secret-value")))
    with patch("monarch_cli.commands.auth.MonarchMoney", return_value=client):
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--email",
                "me@example.com",
                "--password-file",
                str(secret),
                "--storage",
                "file",
            ],
        )
    assert result.exit_code == 1
    assert "secret-value" not in result.stdout
    assert "monarch auth login" in result.stdout


def test_auth_setup_is_structured():
    result = runner.invoke(app, ["auth", "setup", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "--password-file" in str(data)
    assert "--mfa-code" in str(data)
    assert result.stderr == ""


def test_bare_invocation_reads_live_accounts_and_review_count():
    client = MagicMock(
        get_accounts=AsyncMock(
            return_value={
                "accounts": [{"id": "a1", "isHidden": False}, {"id": "a2", "isHidden": True}]
            }
        ),
        get_transactions=AsyncMock(
            return_value={"allTransactions": {"totalCount": 7, "results": []}}
        ),
    )
    with patch("monarch_cli.core.dashboard.get_authenticated_client", return_value=client):
        result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    assert "account_count: 2" in result.stdout
    assert "needs_review_count: 7" in result.stdout
    assert "monarch transactions list --needs-review" in result.stdout
    assert "Usage:" not in result.stdout
    assert client.get_accounts.await_count == 1
    assert client.get_transactions.await_count == 1


def test_bare_invocation_without_auth_has_useful_state():
    with patch(
        "monarch_cli.core.dashboard.get_authenticated_client", side_effect=AuthenticationError
    ):
        result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    assert "auth_required" in result.stdout
    assert "--email" in result.stdout and "--password-file" in result.stdout
    assert "Usage:" not in result.stdout


def test_dashboard_malformed_data_is_not_invented_empty_state():
    client = MagicMock(get_accounts=AsyncMock(return_value={}))
    with patch("monarch_cli.core.dashboard.get_authenticated_client", return_value=client):
        result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert "error: true" in result.stdout


def test_capabilities_default_is_structured_and_exit_contract_is_012():
    result = runner.invoke(app, ["capabilities"])
    assert result.exit_code == 0
    assert "contract_version:" in result.stdout
    result = runner.invoke(app, ["capabilities", "--json"])
    assert set(json.loads(result.stdout)["exit_codes"]) == {"0", "1", "2"}
