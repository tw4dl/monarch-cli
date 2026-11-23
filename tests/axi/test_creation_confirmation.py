"""Creation commands cannot treat arbitrary SDK dictionaries as success."""

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize("kind", ["account", "tag", "attachment"])
@pytest.mark.parametrize("failure", ["missing", "rejected", "no_id"])
def test_unconfirmed_creation_fails(kind, failure, tmp_path):
    client = AsyncMock()
    if kind == "account":
        module, method, root, record = (
            "accounts",
            "create_manual_account",
            "createManualAccount",
            "account",
        )
        words = ["accounts", "create", "--name", "New", "--type", "cash", "--subtype", "checking"]
    elif kind == "tag":
        module, method, root, record = (
            "transactions",
            "create_transaction_tag",
            "createTransactionTag",
            "tag",
        )
        words = ["transactions", "tags", "create", "--name", "New", "--color", "#112233"]
    else:
        module, method, root, record = (
            "transactions",
            "upload_attachment",
            "addTransactionAttachment",
            "attachment",
        )
        receipt = tmp_path / "receipt.pdf"
        receipt.write_bytes(b"%PDF synthetic")
        words = ["transactions", "attach", "123", str(receipt), "--notes", "new"]
    payload = {record: {"id": "new"}}
    if failure == "rejected":
        payload["errors"] = [{"message": "SECRET backend"}]
    if failure == "no_id":
        payload[record] = {}
    getattr(client, method).return_value = {} if failure == "missing" else {root: payload}
    with patch(f"monarch_cli.commands.{module}.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, [*words, "--json"])
    assert result.exit_code == 1
    assert "SECRET" not in result.stdout
    getattr(client, method).assert_awaited_once()
    client.update_transaction.assert_not_called()


@pytest.mark.parametrize(
    "words,module",
    [
        (
            [
                "accounts",
                "create",
                "--name",
                "New",
                "--type",
                "cash",
                "--subtype",
                "checking",
                "--balance",
                "nan",
            ],
            "accounts",
        ),
        (["transactions", "tags", "create", "--name", "", "--color", "#112233"], "transactions"),
        (["transactions", "tags", "create", "--name", "New", "--color", "bad"], "transactions"),
    ],
)
def test_invalid_creation_input_fails_before_auth(words, module):
    with patch(f"monarch_cli.commands.{module}.get_authenticated_client") as auth:
        result = CliRunner().invoke(app, [*words, "--json"])
    assert result.exit_code == 2
    auth.assert_not_called()


@pytest.mark.parametrize("kind", ["account", "tag"])
def test_creation_uses_real_sdk_payload(kind):
    import json

    from monarchmoney import MonarchMoney

    client = MonarchMoney(token="synthetic")

    async def gql_call(**kwargs):
        values = kwargs["variables"]["input"]
        if kind == "account":
            assert kwargs["operation"] == "Web_CreateManualAccount"
            assert values == {
                "name": "New",
                "type": "cash",
                "subtype": "checking",
                "displayBalance": 0,
                "includeInNetWorth": False,
            }
            return {"createManualAccount": {"errors": None, "account": {"id": "new"}}}
        assert kwargs["operation"] == "Common_CreateTransactionTag"
        assert values == {"name": "New", "color": "#AABBCC"}
        return {
            "createTransactionTag": {
                "errors": [],
                "tag": {"id": "new", "name": "New", "color": "#aabbcc"},
            }
        }

    client.gql_call = gql_call
    if kind == "account":
        module = "accounts"
        words = [
            "accounts",
            "create",
            "--name",
            "New",
            "--type",
            "cash",
            "--subtype",
            "checking",
            "--balance",
            "0",
            "--exclude-from-net-worth",
        ]
    else:
        module = "transactions"
        words = ["transactions", "tags", "create", "--name", "New", "--color", "#AABBCC"]
    with patch(f"monarch_cli.commands.{module}.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, [*words, "--json"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["id"] == "new"


def test_attachment_uses_real_sdk_binding_with_stubbed_upload(tmp_path):
    import json

    from monarchmoney import MonarchMoney

    receipt = tmp_path / "receipt.pdf"
    receipt.write_bytes(b"%PDF synthetic")
    client = MonarchMoney(token="synthetic")
    client._get_transaction_attachment_upload_info = AsyncMock(
        return_value={
            "getTransactionAttachmentUploadInfo": {
                "info": {
                    "requestParams": {
                        "timestamp": 1,
                        "folder": "synthetic",
                        "signature": "synthetic",
                        "api_key": "synthetic",
                        "upload_preset": "synthetic",
                    }
                }
            }
        }
    )
    client._upload_form_data = AsyncMock(
        return_value={"public_id": "synthetic", "format": "pdf", "bytes": 14}
    )

    async def gql_call(**kwargs):
        assert kwargs["operation"] == "Common_AddTransactionAttachment"
        values = kwargs["variables"]["input"]
        assert values["transactionId"] == "123"
        assert values["filename"] == "receipt.pdf"
        return {
            "addTransactionAttachment": {
                "errors": [],
                "attachment": {"id": "a1", "filename": values["filename"]},
            }
        }

    client.gql_call = gql_call
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["transactions", "attach", "123", str(receipt), "--json"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["status"] == "attached"
    client._upload_form_data.assert_awaited_once()
