"""Empty opaque results are explicit; missing native responses are errors."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize("payload", [{}, None])
def test_empty_raw_api_data_has_context_and_preserves_explicit_json(payload):
    client = AsyncMock()
    client.gql_call.return_value = payload
    words = ["api", "Empty", "--query", "query Empty { accounts @skip(if: true) { id } }"]
    with patch("monarch_cli.commands.api.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, words)
        legacy = CliRunner().invoke(app, [*words, "--json"])
    assert result.exit_code == 0
    assert "status: empty" in result.stdout and "count: 0" in result.stdout
    assert "No data returned by api." in result.stdout
    assert json.loads(legacy.stdout) == payload


@pytest.mark.parametrize("flags", [[], ["--json"]])
def test_missing_native_credit_response_is_not_empty_success(flags):
    client = AsyncMock()
    client.get_credit_history.return_value = {}
    with patch("monarch_cli.commands.cashflow.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["cashflow", "credit-history", *flags])
    assert result.exit_code == 1


def test_empty_cached_result_is_definitive_without_any_api():
    from monarch_cli.core.result_cache import save_result

    identity = save_result({})
    with patch(
        "monarch_cli.core.adapter.get_authenticated_client", side_effect=AssertionError("no API")
    ):
        result = CliRunner().invoke(app, ["result", "show", identity])
    assert result.exit_code == 0
    assert "No data returned by result show." in result.stdout
