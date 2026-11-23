"""Compact, read-only live state for bare CLI invocation and session context."""

from typing import Any

from .adapter import get_authenticated_client
from .async_utils import run_api_call
from .exceptions import APIError, AuthenticationError


def dashboard() -> dict[str, Any]:
    """Read real account availability and review backlog, without financial details."""
    from ..commands.auth import LOGIN_COMMAND

    try:
        client = get_authenticated_client()
    except AuthenticationError:
        return {"status": "auth_required", "help": [LOGIN_COMMAND, "monarch auth status --json"]}
    raw: Any = run_api_call(lambda: client.get_accounts())
    if not isinstance(raw, dict) or not isinstance(raw.get("accounts"), list):
        raise APIError("Account response is missing its account list")
    accounts = raw["accounts"]
    if any(not isinstance(row, dict) for row in accounts):
        raise APIError("Account response contains invalid account records")
    reviews: Any = run_api_call(lambda: client.get_transactions(limit=1, needs_review=True))
    page = reviews.get("allTransactions") if isinstance(reviews, dict) else None
    total = page.get("totalCount") if isinstance(page, dict) else None
    if type(total) is not int or total < 0:
        raise APIError("Review queue response is missing its total count")
    return {
        "status": "connected",
        "account_count": len(accounts),
        "needs_review_count": total,
        "help": [
            "monarch accounts list",
            "monarch transactions list --needs-review",
            "monarch receipts inbox --status pending_matches",
        ],
    }
