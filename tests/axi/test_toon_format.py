"""TOON output boundary and explicit legacy format compatibility."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from monarch_cli.core.config import Config, reset_config
from monarch_cli.main import app
from monarch_cli.output import OutputFormat, output, set_default_format, set_quiet


@pytest.fixture(autouse=True)
def reset_output():
    reset_config()
    set_default_format(None)
    set_quiet(False)
    yield
    reset_config()
    set_default_format(None)
    set_quiet(False)


def test_explicit_toon_output(capsys):
    output([{"id": "a", "name": "Checking"}], OutputFormat.TOON)
    result = capsys.readouterr()
    assert result.out == "[1]{id,name}:\n  a,Checking\n"
    assert result.err == ""


def test_explicit_toon_command_no_auth():
    with patch("monarch_cli.commands.report.get_authenticated_client") as client:
        result = CliRunner().invoke(
            app, ["report", "create", "--name", "Example", "--dry-run", "--format", "toon"]
        )
    assert result.exit_code == 0, result.output
    assert "status: dry_run" in result.stdout
    assert result.stderr == ""
    client.assert_not_called()


def test_json_compatibility(capsys):
    value = {"id": "a", "amount": 42.0, "notes": "a" * 2000, "extra": [1, 2]}
    output(value, OutputFormat.JSON)
    assert json.loads(capsys.readouterr().out) == value


def test_csv_compatibility(capsys):
    output([{"id": "a", "name": "Checking"}], OutputFormat.CSV)
    assert capsys.readouterr().out.splitlines() == ["id,name", "a,Checking"]


def test_toon_environment_format(monkeypatch, tmp_path):
    monkeypatch.setenv("MONARCH_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("MONARCH_FORMAT", "toon")
    assert Config.load().format == "toon"
