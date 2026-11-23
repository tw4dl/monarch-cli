"""Missing backend collections must never become successful empty lists."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "words,module,method,payload",
    [
        (["accounts", "list"], "monarch_cli.services.accounts", "get_accounts", {}),
        (
            ["categories", "list"],
            "monarch_cli.commands.categories",
            "get_transaction_categories",
            {},
        ),
        (["budgets", "list"], "monarch_cli.commands.budgets", "get_budgets", {}),
        (["transactions", "list"], "monarch_cli.commands.transactions", "get_transactions", {}),
        (
            ["transactions", "list"],
            "monarch_cli.commands.transactions",
            "get_transactions",
            {"allTransactions": {"results": []}},
        ),
        (
            ["investments", "securities", "VTI"],
            "monarch_cli.commands.investments",
            "gql_call",
            {"securities": None},
        ),
    ],
)
def test_missing_backend_collection_is_an_error_even_for_explicit_json(
    words, module, method, payload
):
    client = MagicMock()
    setattr(client, method, AsyncMock(return_value=payload))
    with patch(module + ".get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, [*words, "--json"])
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"] is True
