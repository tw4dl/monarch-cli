"""Public cancellation follows the documented structured 0/1/2 contract."""

import json
from unittest.mock import patch

from typer.testing import CliRunner

from monarch_cli.main import app


def test_public_interrupt_is_structured_and_does_not_replay_write():
    with patch(
        "monarch_cli.commands.transactions.get_authenticated_client", side_effect=KeyboardInterrupt
    ):
        result = CliRunner().invoke(app, ["transactions", "delete", "123", "--yes", "--json"])
    assert result.exit_code == 1
    error = json.loads(result.stdout)
    assert error["error"] is True
    assert "interrupt" in error["message"].lower()
    assert "--yes" not in str(error["help"])
    assert "Interrupted." not in result.stderr
    assert "Traceback" not in result.stderr
