"""Translate SDK rejection details into safe CLI messages and scoped reads."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from monarch_cli.main import app

SECRET = "monarchmoney SDK PRIVATE_TOKEN"


def test_holding_rejection_hides_dependency_message_and_keeps_account_scope():
    client = MagicMock(
        gql_call=AsyncMock(return_value={"createManualHolding": {"errors": [{"message": SECRET}]}})
    )
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app,
            [
                "investments",
                "holding",
                "create",
                "--account",
                "101",
                "--security",
                "s1",
                "--quantity",
                "1",
                "--json",
            ],
        )
    assert result.exit_code == 1
    assert SECRET not in result.stdout
    data = json.loads(result.stdout)
    assert data["help"] == ["monarch investments holdings --account 101 --detailed --raw --full"]


def test_investment_account_rejection_hides_backend_payload():
    client = MagicMock(
        get_accounts=AsyncMock(return_value={"accounts": []}),
        gql_call=AsyncMock(
            return_value={"createManualInvestmentsAccount": {"errors": [{"message": SECRET}]}}
        ),
    )
    with patch("monarch_cli.commands.accounts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app,
            [
                "accounts",
                "create-investments",
                "--name",
                "Example",
                "--subtype",
                "brokerage",
                "--json",
            ],
        )
    assert result.exit_code == 1
    assert SECRET not in result.stdout
    assert json.loads(result.stdout)["help"] == ["monarch accounts list"]


def test_report_payload_errors_remain_diagnostics_not_stdout():
    client = MagicMock(
        gql_call=AsyncMock(
            side_effect=[
                {"reportConfigurations": []},
                {"createReportConfiguration": {"errors": {"message": SECRET}}},
            ]
        )
    )
    with patch("monarch_cli.commands.report.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["report", "create", "--name", "Example", "--json"])
    assert result.exit_code == 1
    assert SECRET not in result.stdout
    assert json.loads(result.stdout)["help"] == ["monarch report list"]


def test_debug_keeps_raw_rejection_in_stderr_only():
    client = MagicMock(
        gql_call=AsyncMock(return_value={"createManualHolding": {"errors": [{"message": SECRET}]}})
    )
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(
            app,
            [
                "--debug",
                "investments",
                "holding",
                "create",
                "--account",
                "101",
                "--security",
                "s1",
                "--quantity",
                "1",
                "--json",
            ],
        )
    assert result.exit_code == 1
    assert SECRET not in result.stdout
    assert SECRET in result.stderr


def test_keyring_storage_failure_is_translated_and_has_flag_complete_repair(tmp_path):
    import keyring.errors

    password = tmp_path / "password.txt"
    password.write_text("test-password")
    client = MagicMock(token="test-token", login=AsyncMock())
    with (
        patch("monarch_cli.commands.auth.MonarchMoney", return_value=client),
        patch("monarch_cli.commands.auth._is_keyring_available", return_value=True),
        patch(
            "monarch_cli.core.session.keyring.set_password",
            side_effect=keyring.errors.KeyringError(SECRET),
        ),
    ):
        result = CliRunner().invoke(
            app,
            [
                "auth",
                "login",
                "--email",
                "test@example.com",
                "--password-file",
                str(password),
                "--storage",
                "keyring",
                "--json",
            ],
        )
    assert result.exit_code == 1
    assert SECRET not in result.stdout
    assert "--storage file" in str(json.loads(result.stdout)["help"])


def test_missing_report_suggests_listing_ids_instead_of_auth_repair():
    client = MagicMock(gql_call=AsyncMock(return_value={"reportConfigurations": []}))
    with patch("monarch_cli.commands.report.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["report", "show", "missing", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["help"] == ["monarch report list"]


def test_root_not_found_error_remains_structured():
    from monarch_cli.core.exceptions import NotFoundError

    with patch("monarch_cli.main.dashboard", side_effect=NotFoundError("Unavailable")):
        result = CliRunner().invoke(app, ["--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["help"] == ["monarch accounts list"]
