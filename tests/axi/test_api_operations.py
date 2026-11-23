"""Validate selected GraphQL operations before auth and never replay writes."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "document", ["query Other { accounts { id } }", "fragment Fields on Account { id }"]
)
def test_unknown_operation_fails_before_auth(document):
    with patch("monarch_cli.commands.api.get_authenticated_client") as auth:
        response = CliRunner().invoke(app, ["api", "Selected", "--query", document, "--json"])
    assert response.exit_code == 2
    auth.assert_not_called()


@pytest.mark.parametrize("kind,retries", [("query", 3), ("mutation", 0), ("subscription", None)])
def test_api_retry_policy_follows_selected_operation(kind, retries):
    with (
        patch("monarch_cli.commands.api.get_authenticated_client") as auth,
        patch("monarch_cli.commands.api.run_api_call", return_value={}) as call,
    ):
        response = CliRunner().invoke(
            app, ["api", "Selected", "--query", f"{kind} Selected {{ example }}", "--json"]
        )
    if retries is None:
        assert response.exit_code == 2
        auth.assert_not_called()
        call.assert_not_called()
    else:
        assert response.exit_code == 0, response.stdout
        assert call.call_args.kwargs["max_retries"] == retries
