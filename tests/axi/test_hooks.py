"""Native lifecycle registration preserves user settings and scopes context."""

import json
import os
import shlex
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


def test_installs_both_native_apps_once_and_repairs_path(tmp_path):
    from monarch_cli.core.hooks import install_hooks

    codex = tmp_path / "codex"
    claude = tmp_path / "claude"
    state = tmp_path / "state"
    scope = tmp_path / "project"
    scope.mkdir()
    codex.mkdir()
    claude.mkdir()
    other = {"type": "command", "command": "/existing/policy"}
    (codex / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"hooks": [other]}]}}))
    (codex / "config.toml").write_text("[features]\nhooks = false # keep comment\napps = true\n")
    (claude / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Read"]}}))
    kwargs = {"codex_home": codex, "claude_home": claude, "state_dir": state, "cwd": scope}
    install_hooks(["/absolute/monarch old"], **kwargs)
    paths = [
        codex / "hooks.json",
        codex / "config.toml",
        claude / "settings.json",
        state / "hooks.json",
    ]
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    install_hooks(["/absolute/monarch old"], **kwargs)
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    install_hooks(["/new path/monarch"], **kwargs)
    for home, filename in [(codex, "hooks.json"), (claude, "settings.json")]:
        data = json.loads((home / filename).read_text())
        for event in ["SessionStart", "Stop" if home == codex else "SessionEnd"]:
            handlers = [h for group in data["hooks"][event] for h in group["hooks"]]
            assert len(handlers) == 1
            argv = shlex.split(handlers[0]["command"])
            assert argv[0] == "/new path/monarch"
            assert "_session-hook" in argv
    assert json.loads((codex / "hooks.json").read_text())["hooks"]["PreToolUse"][0]["hooks"] == [
        other
    ]
    assert json.loads((claude / "settings.json").read_text())["permissions"] == {"allow": ["Read"]}
    assert "hooks = true # keep comment" in (codex / "config.toml").read_text()
    assert "apps = true" in (codex / "config.toml").read_text()


@pytest.mark.parametrize("bad", ["{", "[]", '{"hooks": []}', '{"hooks": {"SessionStart": {}}}'])
def test_invalid_config_is_preserved(tmp_path, bad):
    from monarch_cli.core.hooks import install_hooks

    codex = tmp_path / "codex"
    codex.mkdir()
    target = codex / "hooks.json"
    target.write_text(bad)
    with pytest.raises(ValueError):
        install_hooks(
            ["/bin/monarch"],
            codex_home=codex,
            claude_home=tmp_path / "claude",
            state_dir=tmp_path / "state",
            cwd=tmp_path / "project",
        )
    assert target.read_text() == bad


def test_scoped_start_reads_live_state_and_no_api_outside_scope(tmp_path, monkeypatch):
    from monarch_cli.core.hook_runtime import run_hook
    from monarch_cli.core.hooks import install_hooks

    state = tmp_path / "state"
    scope = tmp_path / "project"
    scope.mkdir()
    install_hooks(
        ["/bin/monarch"],
        codex_home=tmp_path / "codex",
        claude_home=tmp_path / "claude",
        state_dir=state,
        cwd=scope,
    )
    with patch(
        "monarch_cli.core.hook_runtime.dashboard",
        return_value={"status": "connected", "account_count": 2},
    ) as live:
        assert run_hook({"cwd": str(tmp_path), "hook_event_name": "SessionStart"}, state) is None
        live.assert_not_called()
        data = run_hook({"cwd": str(scope), "hook_event_name": "SessionStart"}, state)
        assert data["account_count"] == 2
        live.assert_called_once()
        nested = scope / "nested"
        nested.mkdir()
        assert (
            run_hook({"cwd": str(nested), "hook_event_name": "SessionStart"}, state)[
                "account_count"
            ]
            == 2
        )
        link = scope / "link"
        link.symlink_to(tmp_path, target_is_directory=True)
        assert run_hook({"cwd": str(link), "hook_event_name": "SessionStart"}, state) is None
    monkeypatch.setenv("MONARCH_CONFIG_DIR", str(state))
    result = CliRunner().invoke(
        app,
        ["_session-hook"],
        input=json.dumps({"cwd": str(tmp_path), "hook_event_name": "SessionStart"}),
    )
    assert result.exit_code == 0, result.output
    assert result.stdout == ""


def test_capture_metadata_and_include_it_next_session(tmp_path):
    from monarch_cli.core.hook_runtime import run_hook
    from monarch_cli.core.hooks import install_hooks

    state = tmp_path / "state"
    scope = tmp_path / "project"
    scope.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": "PRIVATE PASSWORD",
                },
            }
        )
        + "\n"
    )
    install_hooks(
        ["/bin/monarch"],
        codex_home=tmp_path / "codex",
        claude_home=tmp_path / "claude",
        state_dir=state,
        cwd=scope,
    )
    event = {
        "cwd": str(scope),
        "hook_event_name": "SessionEnd",
        "session_id": "example",
        "transcript_path": str(transcript),
    }
    with patch("monarch_cli.core.hook_runtime.changed_files", return_value=["src/file.py"]):
        assert run_hook(event, state) is None
    saved = json.loads((state / "hook-history.json").read_text())
    assert "PRIVATE PASSWORD" not in str(saved)
    assert "src/file.py" in str(saved)
    assert str(transcript) in str(saved)
    with patch("monarch_cli.core.hook_runtime.dashboard", return_value={"status": "connected"}):
        context = run_hook({"cwd": str(scope), "hook_event_name": "SessionStart"}, state)
    assert context["previous_session"]["working_tree_file_count"] == 1
    assert context["previous_session"]["tool_calls"] == 1
    assert len(str(context)) < 2000
    assert os.stat(state / "hook-history.json").st_mode & 0o777 == 0o600


def test_hook_malformed_input_is_quiet_and_never_blocks():
    result = CliRunner().invoke(app, ["_session-hook"], input="{bad")
    assert result.exit_code == 0
    assert result.stdout == ""


def test_public_invocation_self_installs_but_hook_does_not():
    with patch("monarch_cli.core.hooks.auto_install") as install:
        result = CliRunner().invoke(app, ["auth", "setup"])
        assert result.exit_code == 0
        install.assert_called_once()
        install.reset_mock()
        result = CliRunner().invoke(app, ["_session-hook"], input="{}")
        assert result.exit_code == 0
        install.assert_not_called()


def test_auto_install_respects_agent_dirs_and_active_absolute_executable(tmp_path, monkeypatch):
    from monarch_cli.core.hooks import auto_install

    monkeypatch.delenv("MONARCH_HOOKS_DISABLED")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("MONARCH_CONFIG_DIR", str(tmp_path / "state"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["/absolute/bin/monarch", "auth", "setup"])
    auto_install()
    data = json.loads((tmp_path / "codex/hooks.json").read_text())
    command = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert shlex.split(command) == [
        "/absolute/bin/monarch",
        "_session-hook",
        "--state-dir",
        str(tmp_path / "state"),
    ]


def test_disabled_auto_install_has_no_side_effects(tmp_path, monkeypatch):
    from monarch_cli.core.hooks import auto_install

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    auto_install()
    assert not (tmp_path / "codex").exists()


def test_stop_protocol_is_json_and_records_no_continuation(tmp_path, monkeypatch):
    monkeypatch.setenv("MONARCH_CONFIG_DIR", str(tmp_path))
    result = CliRunner().invoke(
        app, ["_session-hook"], input=json.dumps({"cwd": str(tmp_path), "hook_event_name": "Stop"})
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {}


def test_native_command_survives_paths_with_spaces_in_real_process(tmp_path):
    import subprocess
    import sys

    from monarch_cli.core.hooks import install_hooks

    state = tmp_path / "state with spaces"
    scope = tmp_path / "project"
    scope.mkdir()
    install_hooks(
        [sys.executable, "-m", "monarch_cli.main"],
        codex_home=tmp_path / "codex",
        claude_home=tmp_path / "claude",
        state_dir=state,
        cwd=scope,
    )
    data = json.loads((tmp_path / "claude/settings.json").read_text())
    command = data["hooks"]["SessionEnd"][0]["hooks"][0]["command"]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")}
    result = subprocess.run(
        command,
        shell=True,
        input=json.dumps({"cwd": str(scope), "hook_event_name": "SessionEnd"}),
        capture_output=True,
        text=True,
        cwd=scope,
        env=env,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert (state / "hook-history.json").exists()


def test_large_transcript_counts_are_explicitly_partial(tmp_path):
    from monarch_cli.core.hook_runtime import run_hook
    from monarch_cli.core.hooks import install_hooks

    state = tmp_path / "state"
    scope = tmp_path / "project"
    scope.mkdir()
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("x" * 300000 + "\n" + json.dumps({"type": "function_call"}) + "\n")
    install_hooks(
        ["/bin/monarch"],
        codex_home=tmp_path / "codex",
        claude_home=tmp_path / "claude",
        state_dir=state,
        cwd=scope,
    )
    run_hook(
        {"cwd": str(scope), "hook_event_name": "SessionEnd", "transcript_path": str(transcript)},
        state,
    )
    with patch("monarch_cli.core.hook_runtime.dashboard", return_value={"status": "connected"}):
        result = run_hook({"cwd": str(scope), "hook_event_name": "SessionStart"}, state)
    assert result["previous_session"]["tool_calls"] == 1
    assert result["previous_session"]["transcript_count_is_tail"] is True
