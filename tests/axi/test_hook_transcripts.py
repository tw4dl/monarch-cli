"""Native Codex custom tool calls count as calls, not output records."""

import json

import pytest

from monarch_cli.core.hook_runtime import _transcript_metadata


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("function_call", 1),
        ("custom_tool_call", 1),
        ("tool_use", 1),
        ("custom_tool_call_output", 0),
        ("function_call_output", 0),
    ],
)
def test_native_tool_record_shapes(tmp_path, kind, expected):
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {"type": "response_item", "payload": {"type": kind, "arguments": "PRIVATE_ARGUMENT"}}
        )
        + "\n"
    )
    result = _transcript_metadata(str(transcript))
    assert result["tool_calls"] == expected
    assert "PRIVATE_ARGUMENT" not in json.dumps(result)
