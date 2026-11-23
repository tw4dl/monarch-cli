"""Opt-in real Claude lifecycle test with a local model and synthetic finance data."""

import hashlib
import json
import os
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from monarch_cli.core.hooks import install_hooks


@pytest.mark.skipif(
    os.environ.get("MONARCH_CLAUDE_NATIVE_TESTS") != "1"
    or not os.environ.get("MONARCH_CLAUDE_EXECUTABLE"),
    reason="Set MONARCH_CLAUDE_NATIVE_TESTS=1 and MONARCH_CLAUDE_EXECUTABLE",
)
def test_claude_delivers_scoped_start_context_and_captures_session_end(tmp_path):
    runtime = Path(os.environ["MONARCH_CLAUDE_EXECUTABLE"])
    assert runtime.is_file()
    monarch = Path(
        os.environ.get("MONARCH_NATIVE_EXECUTABLE", str(Path(sys.executable).parent / "monarch"))
    )
    assert monarch.is_file()
    scope = tmp_path / "project"
    scope.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    state = tmp_path / "state"
    claude_home = tmp_path / "claude"
    install_hooks(
        [str(monarch.resolve())],
        codex_home=tmp_path / "codex",
        claude_home=claude_home,
        state_dir=state,
        cwd=scope,
    )
    patch_dir = tmp_path / "synthetic-provider"
    patch_dir.mkdir()
    (patch_dir / "sitecustomize.py").write_text(
        "from monarch_cli.core import hook_runtime\n"
        'hook_runtime.dashboard = lambda: {"status":"connected",'
        '"account_count":321,"needs_review_count":1}\n'
    )
    observed = []

    class LocalModel(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            assert length < 2_000_000
            raw = self.rfile.read(length)
            body = json.loads(raw)
            observed.append(
                {
                    "path": self.path.split("?")[0],
                    "context": b"account_count: 321" in raw,
                    "user_agent": self.headers.get("User-Agent"),
                }
            )
            if self.path.startswith("/v1/messages/count_tokens"):
                result = {"input_tokens": 1}
            else:
                assert self.path.startswith("/v1/messages"), self.path
                result = {
                    "id": "msg_native_fixture",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "OK"}],
                    "model": "claude-sonnet-4-6",
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            if body.get("stream") and "content" in result:
                events = [
                    {
                        "type": "message_start",
                        "message": {**result, "content": [], "stop_reason": None},
                    },
                    {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": {"type": "text", "text": ""},
                    },
                    {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": "OK"},
                    },
                    {"type": "content_block_stop", "index": 0},
                    {
                        "type": "message_delta",
                        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                        "usage": {"output_tokens": 1},
                    },
                    {"type": "message_stop"},
                ]
                payload = "".join(
                    f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events
                ).encode()
                content_type = "text/event-stream"
            else:
                payload = json.dumps(result).encode()
                content_type = "application/json"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalModel)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "CLAUDE_CODE_"))}
    env.update(
        {
            "CLAUDE_CONFIG_DIR": str(claude_home),
            "ANTHROPIC_API_KEY": "synthetic-local-only",
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_port}",
            "ANTHROPIC_CUSTOM_HEADERS": "User-Agent: OpenAI File Downloader, XaiImageApiFetch/1.0",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "DISABLE_AUTOUPDATER": "1",
            "PYTHONPATH": str(patch_dir),
        }
    )
    try:
        for cwd, wants_context in [(scope, True), (outside, False)]:
            observed.clear()
            session = str(uuid.uuid4())
            command = [
                str(runtime),
                "-p",
                "Return OK.",
                "--restricted",
                "--tools",
                "",
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--settings",
                str(claude_home / "settings.json"),
                "--setting-sources",
                "",
                "--system-prompt",
                "Native lifecycle verification.",
                "--model",
                "claude-sonnet-4-6",
                "--output-format",
                "json",
                "--session-id",
                session,
            ]
            result = subprocess.run(
                command, cwd=cwd, env=env, capture_output=True, text=True, timeout=45
            )
            assert result.returncode == 0, result.stderr[-2000:] + result.stdout[-2000:]
            assert json.loads(result.stdout)["result"] == "OK"
            assert any(item["path"] == "/v1/messages" for item in observed)
            assert any(item["context"] for item in observed) == wants_context
            assert all(
                item["user_agent"] == "OpenAI File Downloader, XaiImageApiFetch/1.0"
                for item in observed
            )
            history = json.loads((state / "hook-history.json").read_text())
            assert str(outside) not in history
            if wants_context:
                record = history[str(scope)]
                assert record["event"] == "SessionEnd"
                assert record["session_hash"] == hashlib.sha256(session.encode()).hexdigest()[:16]
                assert record["transcript_bytes"] > 0
                assert "Return OK." not in json.dumps(record)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
