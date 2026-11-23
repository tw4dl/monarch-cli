"""Opt-in native schema/trust check. No model turn, credentials, or financial calls."""

import json
import os
import selectors
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from monarch_cli.core.hooks import install_hooks


@pytest.mark.skipif(
    os.environ.get("MONARCH_NATIVE_HOOK_TESTS") != "1" or not shutil.which("codex"),
    reason="Set MONARCH_NATIVE_HOOK_TESTS=1 with a local Codex runtime",
)
def test_installed_codex_loads_registered_native_hooks(tmp_path):
    scope = tmp_path / "project"
    scope.mkdir()
    executable = str(Path(__file__).resolve().parents[2] / ".venv/bin/monarch")
    install_hooks(
        [executable],
        codex_home=tmp_path / "codex",
        claude_home=tmp_path / "claude",
        state_dir=tmp_path / "state",
        cwd=scope,
    )
    env = {**os.environ, "CODEX_HOME": str(tmp_path / "codex")}
    with (tmp_path / "codex-stderr.log").open("w") as stderr:
        process = subprocess.Popen(
            ["codex", "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            env=env,
        )
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)

        def request(identifier, method, params):
            process.stdin.write(
                json.dumps({"id": identifier, "method": method, "params": params}) + "\n"
            )
            process.stdin.flush()
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if not selector.select(timeout=1):
                    continue
                line = process.stdout.readline()
                assert line, "Native app server ended before its response"
                message = json.loads(line)
                if message.get("id") == identifier:
                    assert "error" not in message, message
                    return message["result"]
            pytest.fail(f"Native hook validation timed out: {method}")

        try:
            request(
                1,
                "initialize",
                {
                    "clientInfo": {"name": "monarch-axi-conformance", "version": "1"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            process.stdin.write(json.dumps({"method": "initialized", "params": {}}) + "\n")
            process.stdin.flush()
            result = request(2, "hooks/list", {"cwds": [str(scope)]})
            entries = result["data"]
            assert len(entries) == 1
            assert entries[0]["errors"] == []
            assert entries[0]["warnings"] == []
            hooks = entries[0]["hooks"]
            assert {item["eventName"] for item in hooks} == {"sessionStart", "stop"}
            assert all(item["enabled"] and item["source"] == "user" for item in hooks)
            # Native review belongs to the user; never manufacture trust to pass this test.
            assert all(item["trustStatus"] == "untrusted" for item in hooks)
        finally:
            selector.close()
            process.stdin.close()
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            process.stdout.close()
