"""Default retries must never replay a public write-capable command."""

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from monarch_cli.main import app


def test_attachment_timeout_does_not_replay_upload(tmp_path):
    receipt = tmp_path / "receipt.pdf"
    receipt.write_bytes(b"%PDF synthetic")
    client = AsyncMock()
    client.upload_attachment.side_effect = TimeoutError("SECRET connection")
    with (
        patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client),
        patch("monarch_cli.core.async_utils.asyncio.sleep", new=AsyncMock()),
    ):
        result = CliRunner().invoke(app, ["transactions", "attach", "123", str(receipt), "--json"])
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    client.upload_attachment.assert_awaited_once()


def test_read_only_command_keeps_configured_retries():
    client = AsyncMock()
    client.get_accounts.side_effect = [TimeoutError(), {"accounts": []}]
    with (
        patch("monarch_cli.services.accounts.get_authenticated_client", return_value=client),
        patch("monarch_cli.core.async_utils.asyncio.sleep", new=AsyncMock()),
    ):
        result = CliRunner().invoke(app, ["accounts", "list", "--json"])
    assert result.exit_code == 0, result.stdout
    assert client.get_accounts.await_count == 2
