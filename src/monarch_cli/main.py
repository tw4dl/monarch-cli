"""Monarch CLI entry point."""

from typing import cast

import typer
from typer.main import get_command

from monarch_cli import __version__
from monarch_cli.commands import (
    accounts,
    api,
    auth,
    budgets,
    cashflow,
    categories,
    investments,
    mcp,
    receipts,
    report,
    result,
    transactions,
)
from monarch_cli.commands.agent_hooks import session_hook
from monarch_cli.core.agent_cli import AgentGroup
from monarch_cli.core.agent_context import options as agent_options
from monarch_cli.core.capabilities import build_capabilities
from monarch_cli.core.config import Config, FormatType, set_config
from monarch_cli.core.dashboard import dashboard
from monarch_cli.core.error_handler import handle_errors
from monarch_cli.output import OutputFormat, apply_config, output

app = typer.Typer(
    name="monarch",
    cls=AgentGroup,
    help="CLI for Monarch Money",
    no_args_is_help=False,
    invoke_without_command=True,
    epilog="Exit codes: 0 success; 1 general error; 2 usage or input error.",
)

# Register command groups
app.add_typer(auth.app, name="auth")
app.add_typer(accounts.app, name="accounts")
app.add_typer(transactions.app, name="transactions")
app.add_typer(budgets.app, name="budgets")
app.add_typer(cashflow.app, name="cashflow")
app.add_typer(categories.app, name="categories")
app.command("api")(api.api_cmd)
app.add_typer(investments.app, name="investments")
app.add_typer(mcp.app, name="mcp")
app.add_typer(receipts.app, name="receipts")
app.add_typer(report.app, name="report")
app.add_typer(result.app, name="result")
app.command("_session-hook", hidden=True)(session_hook)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"monarch-cli {__version__}")
        raise typer.Exit()


@app.callback()
@handle_errors
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(  # noqa: ARG001
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show operational progress messages.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show stack traces on errors (implies --verbose).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output the complete JSON schema.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Output only IDs, one per line (for AI agent consumption).",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable colored output.",
    ),
    timeout: int | None = typer.Option(
        None,
        "--timeout",
        help="API request timeout in seconds.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Fail instead of prompting for input.",
    ),
) -> None:
    """CLI for Monarch Money - AI-agent friendly financial data access."""
    # Load config from file and env vars
    config = Config.load()

    if config.get_source("format") == "default":
        config = config.with_overrides(format="toon")
    requested_format = cast(FormatType | None, agent_options().get("format"))

    # Apply CLI flag overrides
    config = config.with_overrides(
        verbose=verbose if verbose else None,
        debug=debug if debug else None,
        format="json" if json_output else requested_format,
        quiet=quiet if quiet else None,
        color=False if no_color else None,
        timeout_seconds=timeout,
        non_interactive=non_interactive if non_interactive else None,
    )

    # Set the global config with overrides applied
    set_config(config)

    # Apply config to output system
    apply_config(config)
    if ctx.invoked_subcommand is None:
        output(dashboard())


@app.command()
def capabilities(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output the capabilities manifest as JSON.",
    ),
) -> None:
    """Describe commands, flags, env vars, and exit codes for agents."""
    manifest = build_capabilities(get_command(app), __version__)
    if json_output:
        output(manifest, OutputFormat.JSON)
    else:
        output(manifest)


if __name__ == "__main__":
    app()
