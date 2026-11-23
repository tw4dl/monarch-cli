"""Keep conformance checks isolated from user configuration and agent hooks."""

import pytest

from monarch_cli.core.config import reset_config
from monarch_cli.output import set_default_format, set_quiet


@pytest.fixture(autouse=True)
def isolated_cli_state(monkeypatch, tmp_path):
    monkeypatch.setenv("MONARCH_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("MONARCH_FORMAT", raising=False)
    monkeypatch.setenv("MONARCH_HOOKS_DISABLED", "1")
    reset_config()
    set_default_format(None)
    set_quiet(False)
    yield
    reset_config()
    set_default_format(None)
    set_quiet(False)
