"""Full mutation output can be recovered without replaying a financial write."""

import json
import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app


def test_private_cache_and_read_only_full_command(tmp_path):
    from monarch_cli.core.result_cache import save_result

    data = {"id": "created", "notes": "A" * 2000}
    identity = save_result(data)
    assert len(identity) == 32
    path = tmp_path / "results" / f"{identity}.json"
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(path.parent).st_mode & 0o777 == 0o700
    with patch(
        "monarch_cli.core.adapter.get_authenticated_client", side_effect=AssertionError("no API")
    ):
        result = CliRunner().invoke(app, ["result", "show", identity, "--full", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == data


@pytest.mark.parametrize("identity", ["../session", "/etc/passwd", "bad"])
def test_cache_ids_cannot_read_arbitrary_files(identity):
    result = CliRunner().invoke(app, ["result", "show", identity])
    assert result.exit_code == 2


def test_cache_is_bounded(tmp_path):
    from monarch_cli.core.result_cache import load_result, save_result

    for i in range(25):
        latest = save_result({"id": str(i)})
    assert len(list((tmp_path / "results").glob("*.json"))) == 20
    assert load_result(latest)["id"] == "24"


def test_large_mutation_result_hint_reads_cache_without_repeating_write():
    import shlex
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock(gql_call=AsyncMock(return_value={"receipt": "R" * 2000}))
    with patch("monarch_cli.commands.api.get_authenticated_client", return_value=client):
        response = CliRunner().invoke(
            app, ["api", "Example", "--query", "mutation Example { unused }"]
        )
    assert response.exit_code == 0, response.output
    assert "truncated, 2000 chars total" in response.stdout
    import re

    identity = re.search(r"monarch result show ([a-f0-9]{32}) --full", response.stdout).group(1)
    full = CliRunner().invoke(app, shlex.split(f"monarch result show {identity} --full --json")[1:])
    assert full.exit_code == 0
    assert json.loads(full.stdout) == {"receipt": "R" * 2000}
    client.gql_call.assert_awaited_once()


def test_expired_cache_is_not_returned(tmp_path):
    import time

    from monarch_cli.core.result_cache import save_result

    identity = save_result({"id": "old"})
    path = tmp_path / "results" / f"{identity}.json"
    expired = time.time() - 90000
    os.utime(path, (expired, expired))
    result = CliRunner().invoke(app, ["result", "show", identity, "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["help"] == ["monarch result list"]


def test_result_symlink_cannot_read_user_files(tmp_path):
    target = tmp_path / "session.json"
    target.write_text('{"secret":"must not read"}')
    directory = tmp_path / "results"
    directory.mkdir()
    identity = "a" * 32
    (directory / f"{identity}.json").symlink_to(target)
    result = CliRunner().invoke(app, ["result", "show", identity, "--json"])
    assert result.exit_code == 1
    assert "must not read" not in result.stdout


def test_cache_pruning_tolerates_an_entry_removed_by_another_process(tmp_path, monkeypatch):
    from pathlib import Path

    from monarch_cli.core.result_cache import load_result, save_result

    old = save_result({"id": "old"})
    old_path = tmp_path / "results" / f"{old}.json"
    original_stat = Path.stat
    removed = False

    def raced_stat(path, *args, **kwargs):
        nonlocal removed
        if path == old_path and not removed:
            removed = True
            path.unlink()
            raise FileNotFoundError(str(path))
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", raced_stat)
    current = save_result({"id": "new"})
    assert load_result(current) == {"id": "new"}


def test_storage_failure_after_write_explains_uncertain_state_without_replay():
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock(gql_call=AsyncMock(return_value={"receipt": "R" * 2000}))
    with (
        patch("monarch_cli.commands.api.get_authenticated_client", return_value=client),
        patch(
            "monarch_cli.core.result_cache.save_result", side_effect=PermissionError("PRIVATE_PATH")
        ),
    ):
        response = CliRunner().invoke(
            app, ["api", "Example", "--query", "mutation Example { unused }"]
        )
    assert response.exit_code == 1, response.output
    assert "may have completed" in response.stdout
    assert "PRIVATE_PATH" not in response.stdout
    assert "mutation Example" not in response.stdout
    client.gql_call.assert_awaited_once()
