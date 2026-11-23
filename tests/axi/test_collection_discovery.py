"""Default lists reveal relevant read commands without inventing write values."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "words,module,method,payload,hint",
    [
        (
            ["categories", "list"],
            "categories",
            "get_transaction_categories",
            {"categories": [{"id": "cat 1", "name": "Food", "group": {"name": "Expense"}}]},
            "monarch transactions list --category 'cat 1'",
        ),
        (
            ["budgets", "list"],
            "budgets",
            "get_budgets",
            {
                "budgetData": {
                    "monthlyAmountsByCategory": [
                        {
                            "category": {"id": "c1"},
                            "monthlyAmounts": [
                                {
                                    "month": "2026-01-01",
                                    "plannedCashFlowAmount": 10,
                                    "actualAmount": -5,
                                    "remainingAmount": 5,
                                }
                            ],
                        }
                    ]
                }
            },
            "monarch categories list",
        ),
    ],
)
def test_list_discovery(words, module, method, payload, hint):
    client = MagicMock()
    setattr(client, method, AsyncMock(return_value=payload))
    with patch(f"monarch_cli.commands.{module}.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, words)
        original = CliRunner().invoke(app, [*words, "--json"])
    assert result.exit_code == original.exit_code == 0, result.stdout
    assert hint in result.stdout
    assert '"help"' not in original.stdout
