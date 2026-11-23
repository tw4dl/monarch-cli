"""Attachment absence requires a valid response for the requested transaction."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"getTransaction": {"id": "t1"}},
        {"getTransaction": {"id": "other", "attachments": []}},
        {"errors": ["failed"], "getTransaction": {"id": "t1", "attachments": []}},
    ],
)
def test_incomplete_attachment_response_has_targeted_inspection(payload):
    client = MagicMock(get_transaction_details=AsyncMock(return_value=payload))
    with patch("monarch_cli.commands.receipts.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["receipts", "list", "t1", "--json"])
    assert result.exit_code == 1
    value = json.loads(result.stdout)
    assert value["code"] == "API_ERROR"
    assert value["help"] == ["monarch transactions show t1"]
