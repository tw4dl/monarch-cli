"""MCP server exposing the Monarch CLI as tools."""

from __future__ import annotations

import json
from typing import Any

from monarchmoney import MonarchMoney, RequireMFAException  # type: ignore[import-untyped]
from typer.testing import CliRunner

from monarch_cli.commands.auth import _is_keyring_available
from monarch_cli.core.adapter import extract_token_from_client, reset_client
from monarch_cli.core.async_utils import run_async
from monarch_cli.core.session import StorageBackend, save_session_token
from monarch_cli.main import app as monarch_app


def run_monarch_cli(argv: list[str], *, json_output: bool = True) -> dict[str, Any]:
    """Run the `monarch` CLI in-process and return structured output.

    Notes:
    - Blocks interactive commands like `auth login` (use `auth_login` instead).
    - Forces `--json` by default for machine-readable output.
    """
    if len(argv) >= 2 and argv[0] == "auth" and argv[1] == "login":
        raise ValueError("Command is interactive; use `monarch.auth_login` instead.")

    args = list(argv)
    if json_output and "--json" not in args:
        args = ["--json", *args]

    runner = CliRunner()
    result = runner.invoke(monarch_app, args)

    parsed: Any | None = None
    stdout = getattr(result, "stdout", "")
    if json_output and stdout.strip():
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None

    stderr = getattr(result, "stderr", "")
    return {
        "exit_code": result.exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "json": parsed,
    }


def auth_login(
    *,
    email: str,
    password: str,
    mfa_code: str | None = None,
    storage: str | None = None,
) -> dict[str, Any]:
    """Non-interactive Monarch login suitable for MCP tool calls."""
    if storage is None:
        backend = StorageBackend.KEYRING if _is_keyring_available() else StorageBackend.FILE
    else:
        storage_lower = storage.lower()
        if storage_lower == "keyring":
            if not _is_keyring_available():
                return {
                    "status": "error",
                    "error": "keyring_unavailable",
                    "message": "Keyring not available; use storage='file' instead.",
                }
            backend = StorageBackend.KEYRING
        elif storage_lower == "file":
            backend = StorageBackend.FILE
        else:
            return {
                "status": "error",
                "error": "invalid_storage",
                "message": "Invalid storage backend; use 'keyring' or 'file'.",
            }

    mm = MonarchMoney()
    try:
        run_async(mm.login(email, password, use_saved_session=False, save_session=False))
    except RequireMFAException:
        if not mfa_code:
            return {
                "status": "mfa_required",
                "message": "MFA required; re-call with `mfa_code`.",
            }
        try:
            run_async(mm.multi_factor_authenticate(email, password, mfa_code))
        except Exception as e:  # noqa: BLE001
            return {
                "status": "error",
                "error": "mfa_failed",
                "message": f"MFA authentication failed: {e}",
            }
    except Exception as e:  # noqa: BLE001
        return {
            "status": "error",
            "error": "login_failed",
            "message": f"Login failed: {e}",
        }

    token = extract_token_from_client(mm)
    if not token:
        return {
            "status": "error",
            "error": "no_token",
            "message": "Failed to obtain authentication token.",
        }

    save_session_token(token, backend)
    reset_client()

    return {
        "status": "ok",
        "storage_backend": backend.value,
        "message": "Logged in successfully.",
    }


def build_mcp_server() -> object:
    """Create a runnable FastMCP server."""
    from mcp.server.fastmcp import FastMCP  # noqa: PLC0415

    mcp = FastMCP("monarch-cli", json_response=True)

    @mcp.tool(name="monarch.run")
    def tool_run(argv: list[str], json_output: bool = True) -> dict[str, Any]:
        """Run any non-interactive `monarch` CLI command."""
        return run_monarch_cli(argv, json_output=json_output)

    @mcp.tool(name="monarch.auth_login")
    def tool_auth_login(
        email: str,
        password: str,
        mfa_code: str | None = None,
        storage: str | None = None,
    ) -> dict[str, Any]:
        """Log in to Monarch (non-interactive)."""
        return auth_login(email=email, password=password, mfa_code=mfa_code, storage=storage)

    return mcp
