"""Flag-complete authentication and structured diagnostics; never prompt."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

import keyring
import typer
from monarchmoney import MonarchMoney, RequireMFAException  # type: ignore[import-untyped]

from ..core.adapter import extract_token_from_client, get_authenticated_client, reset_client
from ..core.async_utils import run_api_call
from ..core.error_handler import handle_errors
from ..core.exceptions import APIError, AuthenticationError, ValidationError
from ..core.session import (
    StorageBackend,
    delete_session_token,
    get_session_path,
    get_storage_info,
    save_session_token,
)
from ..output import OutputFormat, get_default_format, output

app = typer.Typer(help="Authentication management", no_args_is_help=True)
LOGIN_COMMAND = "monarch auth login --email EMAIL --password-file PASSWORD_FILE --storage file"


def _wants_json(json_output: bool) -> bool:
    return json_output or get_default_format() == OutputFormat.JSON


def _is_keyring_available() -> bool:
    try:
        return "fail" not in type(keyring.get_keyring()).__module__
    except Exception:
        return False


def _get_keyring_backend_name() -> str:
    try:
        return type(keyring.get_keyring()).__name__
    except Exception:
        return "unknown"


def _accounts_count(data: Any) -> int:
    if not isinstance(data, dict) or not isinstance(data.get("accounts"), list):
        raise APIError("Account response is missing its account list")
    return len(data["accounts"])


@app.command()
@handle_errors
def login(
    email: Annotated[
        str, typer.Option("--email", envvar="MONARCH_EMAIL", help="Monarch email address")
    ],
    password_file: Annotated[
        Path | None,
        typer.Option(
            "--password-file",
            exists=True,
            dir_okay=False,
            readable=True,
            help="UTF-8 password file; otherwise use MONARCH_PASSWORD",
        ),
    ] = None,
    mfa_code: Annotated[
        str | None,
        typer.Option("--mfa-code", envvar="MONARCH_MFA_CODE", help="MFA code if required"),
    ] = None,
    storage: Annotated[
        str, typer.Option("--storage", "-s", help="Session storage: keyring or file")
    ] = "keyring",
) -> None:
    """Log in using flags or environment variables, without interactive prompts.

    Examples:
        monarch auth login --email EMAIL --password-file PASSWORD_FILE --storage file
        monarch auth login --email EMAIL --password-file PASSWORD_FILE --mfa-code CODE
    """
    if storage not in {"keyring", "file"}:
        raise ValidationError("Invalid storage backend; use --storage keyring or --storage file")
    if not email.strip():
        raise ValidationError("--email must not be empty")
    if storage == "keyring" and not _is_keyring_available():
        raise ValidationError(
            "Keyring not available; use --storage file", details={"fix": LOGIN_COMMAND}
        )
    try:
        password = (
            password_file.read_text(encoding="utf-8").rstrip("\r\n")
            if password_file
            else os.environ.get("MONARCH_PASSWORD")
        )
    except (OSError, UnicodeError) as exc:
        raise ValidationError("Cannot read --password-file as UTF-8") from exc
    if not password:
        raise ValidationError(
            "Pass a nonempty --password-file or set MONARCH_PASSWORD",
            details={"fix": LOGIN_COMMAND},
        )
    client = MonarchMoney()
    client._headers["User-Agent"] = "OpenAI File Downloader, XaiImageApiFetch/1.0"
    try:
        run_api_call(
            lambda: client.login(
                email.strip(), password, use_saved_session=False, save_session=False
            ),
            max_retries=0,
        )
    except RequireMFAException:
        if not mfa_code:
            raise ValidationError(
                "MFA required; rerun with --mfa-code CODE",
                details={"fix": LOGIN_COMMAND + " --mfa-code CODE"},
            ) from None
        try:
            run_api_call(
                lambda: client.multi_factor_authenticate(email.strip(), password, mfa_code),
                max_retries=0,
            )
        except Exception as exc:
            raise AuthenticationError(
                "MFA login failed; check the code and rerun auth login",
                details={"fix": LOGIN_COMMAND + " --mfa-code CODE"},
            ) from exc
    except Exception as exc:
        raise AuthenticationError(
            "Login failed; check your email and password, or reset your Monarch password",
            details={"fix": LOGIN_COMMAND},
        ) from exc
    token = extract_token_from_client(client)
    if not token:
        raise AuthenticationError("Login returned no session token", details={"fix": LOGIN_COMMAND})
    save_session_token(token, StorageBackend(storage))
    reset_client()
    output({"status": "authenticated", "storage_backend": storage})


@app.command()
@handle_errors
def status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Show stored credential availability; use auth ping to verify the session.

    Examples:
        monarch auth status
        monarch auth status --json
    """
    info = get_storage_info()
    authenticated = info["active_backend"] is not None
    result: dict[str, Any] = {
        "authenticated": authenticated,
        "storage_backend": info["active_backend"],
        "message": "Authenticated and ready"
        if authenticated
        else "Not authenticated. Run 'monarch auth login' to authenticate.",
    }
    if not _wants_json(json_output):
        if info["active_backend"] == "file":
            result["location"] = str(get_session_path())
        elif info["active_backend"] == "env":
            result["location"] = "MONARCH_TOKEN"
        result["help"] = ["monarch auth ping --json" if authenticated else LOGIN_COMMAND]
    output(result, OutputFormat.JSON if _wants_json(json_output) else None)


@app.command()
@handle_errors
def logout(
    storage: Annotated[
        str | None,
        typer.Option("--storage", "-s", help="Clear keyring, file, or file-compat; default all"),
    ] = None,
) -> None:
    """Clear saved credentials; an already empty store is a successful no-op.

    Examples:
        monarch auth logout
        monarch auth logout --storage file
    """
    try:
        backend = StorageBackend(storage.lower()) if storage else None
    except ValueError as exc:
        raise ValidationError("Invalid storage backend; use keyring, file, or file-compat") from exc
    if backend is None and os.environ.get("MONARCH_TOKEN"):
        raise ValidationError(
            "MONARCH_TOKEN is set; unset it before logging out",
            details={"fix": "unset MONARCH_TOKEN"},
        )
    delete_session_token(backend)
    reset_client()
    output({"status": "logged_out", "storage_backend": backend.value if backend else "all"})


@app.command()
@handle_errors
def doctor() -> None:
    """Diagnose storage and live connectivity without exposing credentials.

    Examples:
        monarch auth doctor
        monarch auth doctor --format json
    """
    info = get_storage_info()
    connection: dict[str, Any] = {"status": "skipped", "message": "Not authenticated"}
    if info["active_backend"]:
        try:
            client = get_authenticated_client()
            count = _accounts_count(run_api_call(lambda: client.get_accounts()))
            connection = {"status": "ok", "account_count": count}
        except AuthenticationError:
            connection = {"status": "auth_required", "help": LOGIN_COMMAND}
        except Exception:
            connection = {"status": "error", "help": "monarch auth ping --json"}
    output(
        {
            "keyring": {
                "available": _is_keyring_available(),
                "backend": _get_keyring_backend_name(),
            },
            "storage": info,
            "session_file": str(get_session_path()),
            "connection": connection,
        }
    )


@app.command()
@handle_errors
def ping(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Verify the stored session through a live read-only request.

    Examples:
        monarch auth ping
        monarch auth ping --json
    """
    client = get_authenticated_client()
    try:
        count = _accounts_count(run_api_call(lambda: client.get_accounts()))
    except AuthenticationError:
        raise
    except Exception as exc:
        raise APIError(
            "Connection check failed; verify your network and session with auth doctor"
        ) from exc
    result: dict[str, Any] = {
        "status": "ok",
        "message": f"Connected successfully. {count} accounts available.",
    }
    if not _wants_json(json_output):
        result["account_count"] = count
    output(result, OutputFormat.JSON if _wants_json(json_output) else None)


@app.command()
def setup() -> None:
    """Show complete login and diagnostic commands without opening a browser.

    Examples:
        monarch auth setup
        monarch auth setup --format json
    """
    output(
        {
            "login": LOGIN_COMMAND,
            "mfa": LOGIN_COMMAND + " --mfa-code CODE",
            "storage": {
                "keyring": "OS credential storage",
                "file": str(get_session_path()),
                "env": "MONARCH_TOKEN",
            },
            "help": [
                "monarch auth status --json",
                "monarch auth doctor",
                "monarch auth ping --json",
            ],
        }
    )
