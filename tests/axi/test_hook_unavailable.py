"""Registered sessions receive actionable context when live context fails."""

import json
from unittest.mock import patch

from typer.testing import CliRunner

from monarch_cli.main import app


def test_scoped_start_failure_has_safe_stdout_context(tmp_path):
    scope = tmp_path / "project"
    scope.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    (state / "hooks.json").write_text(json.dumps({"directories": [str(scope)]}))
    with patch(
        "monarch_cli.core.hook_runtime.dashboard", side_effect=RuntimeError("private token")
    ):
        result = CliRunner().invoke(
            app,
            ["_session-hook", "--state-dir", str(state)],
            input=json.dumps({"cwd": str(scope), "hook_event_name": "SessionStart"}),
        )
    assert result.exit_code == 0
    assert "status: unavailable" in result.stdout
    assert "monarch auth doctor" in result.stdout
    assert "private token" not in result.output


def test_unregistered_start_stays_quiet_when_dashboard_unavailable(tmp_path):
    with patch("monarch_cli.core.hook_runtime.dashboard") as dashboard:
        result = CliRunner().invoke(
            app,
            ["_session-hook", "--state-dir", str(tmp_path)],
            input=json.dumps({"cwd": str(tmp_path), "hook_event_name": "SessionStart"}),
        )
    assert result.exit_code == 0
    assert result.stdout == ""
    dashboard.assert_not_called()
