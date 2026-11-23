"""Receipt search dates use local actionable usage errors."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "flags",
    [
        ["--start", "bad"],
        ["--end", "2026-02-30"],
        ["--start", "20260101"],
        ["--start", "2026-02-02", "--end", "2026-02-01"],
    ],
)
@pytest.mark.parametrize("json_flag", [[], ["--json"]])
def test_invalid_receipt_dates_fail_before_auth(flags, json_flag):
    with patch("monarch_cli.commands.receipts.get_authenticated_client") as auth:
        result = CliRunner().invoke(app, ["receipts", "missing", *flags, *json_flag])
    assert result.exit_code == 2, result.stdout
    auth.assert_not_called()
    if json_flag:
        value = json.loads(result.stdout)
        assert value["help"]
    else:
        assert "help" in result.stdout
