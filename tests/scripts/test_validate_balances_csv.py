"""Regression coverage for the migrated offline balance export validator."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_balances_csv.py"


@pytest.mark.parametrize(
    ("content", "code", "message"),
    [
        ("Date,Balance,Account\n2026-01-01,100,Checking\n", 0, "Validation passed."),
        (" date , balance , account \n2026-01-01,100,Checking\n", 0, "Validation passed."),
        ("", 2, "Missing header row."),
        ("Date,Balance\n2026-01-01,100\n", 2, "Missing required columns"),
        ("Date,Balance,Account\n2026-01-01,100\n", 1, "Empty fields: 1"),
        ("Date,Balance,Account\n2026-01-01,,Checking\n", 1, "Empty fields: 1"),
    ],
)
def test_validate_export(tmp_path: Path, content: str, code: int, message: str) -> None:
    source = tmp_path / "balances.csv"
    source.write_text(content)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source)], capture_output=True, text=True
    )
    assert result.returncode == code
    assert message in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_missing_file(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "missing.csv")], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "File not found:" in result.stderr
