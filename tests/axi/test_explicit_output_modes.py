"""Explicit framing retains data contracts and honors field selection."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli import __version__
from monarch_cli.main import app
from monarch_cli.output.toon import encode


def test_version_is_a_valid_toon_scalar():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == encode(f"monarch-cli {__version__}")


@pytest.mark.parametrize(
    "group,module,method,payload",
    [
        (
            "accounts",
            "monarch_cli.services.accounts",
            "get_accounts",
            {"accounts": [{"id": "001", "displayName": "Cash"}]},
        ),
        (
            "transactions",
            "monarch_cli.commands.transactions",
            "get_transactions",
            {
                "allTransactions": {
                    "totalCount": 1,
                    "results": [{"id": "001", "date": "2026-11-01", "amount": 10}],
                }
            },
        ),
    ],
)
def test_ndjson_honors_explicit_fields(group, module, method, payload):
    client = AsyncMock()
    getattr(client, method).return_value = payload
    with patch(f"{module}.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, [group, "list", "--ndjson", "--fields", "id"])
    assert result.exit_code == 0, result.stdout
    assert [json.loads(line) for line in result.stdout.splitlines()] == [{"id": "001"}]
