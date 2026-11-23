"""Pagination bounds are local usage errors before any dependency runs."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "words,module",
    [
        (["transactions", "list", "--limit", "-1"], "transactions"),
        (["transactions", "list", "--limit", "0"], "transactions"),
        (["transactions", "list", "--offset", "-1"], "transactions"),
        (["cashflow", "detail", "--limit", "-1"], "cashflow"),
        (["cashflow", "detail", "--limit", "0"], "cashflow"),
    ],
)
def test_invalid_pagination_fails_before_auth(words, module):
    with patch(
        f"monarch_cli.commands.{module}.get_authenticated_client",
        side_effect=AssertionError("input reached auth"),
    ) as auth:
        result = CliRunner().invoke(app, [*words, "--json"])
    assert result.exit_code == 2, result.stdout
    auth.assert_not_called()
