"""Read cached full results; never call Monarch or replay an operation."""

import typer

from ..core.error_handler import handle_errors
from ..core.result_cache import list_results, load_result
from ..output import output

app = typer.Typer(help="Read private cached write results", no_args_is_help=True)


@app.command("show")
@handle_errors
def show(result_id: str) -> None:
    """Read a cached result by exact ID. Use --full for all content."""
    output(load_result(result_id))


@app.command("list")
@handle_errors
def list_cached() -> None:
    """List available cached result IDs without reading their financial content."""
    output(list_results())
