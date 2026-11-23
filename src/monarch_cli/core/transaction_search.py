"""Complete, validated candidate search before an idempotent transaction create."""

from collections.abc import Iterator
from functools import partial
from math import isfinite
from shlex import join
from typing import Any

from ..transformers.transactions import transform_transaction
from .async_utils import run_api_call
from .exceptions import APIError
from .responses import complete_ids, transaction_page


def dedupe_candidates(
    client: Any, *, date: str, account: str, category: str, fields: list[str]
) -> Iterator[dict[str, Any]]:
    """Search the requested account/day completely, tolerating backend page caps."""
    offset = 0
    expected_total = None
    seen: set[str] = set()
    fix = join(
        ["monarch", "transactions", "list", "--account", account, "--start", date, "--end", date]
    )
    while True:
        raw = run_api_call(
            partial(
                client.get_transactions,
                limit=500,
                offset=offset,
                start_date=date,
                end_date=date,
                search="",
                category_ids=[category] if "category" in fields else [],
                account_ids=[account],
                tag_ids=[],
            )
        )
        rows, total = transaction_page(raw)
        ids = complete_ids(raw, "allTransactions.results")
        if (
            (expected_total is not None and total != expected_total)
            or ids & seen
            or offset + len(rows) > total
        ):
            raise APIError(
                "Transaction search changed or repeated results. Inspect before retrying.",
                details={"fix": fix},
            )
        if not rows and offset < total:
            raise APIError(
                "Transaction search was incomplete. Inspect before creating.", details={"fix": fix}
            )
        expected_total = total
        seen.update(ids)
        for row in rows:
            value = transform_transaction(row)
            if (
                value["account_id"] != account
                or value["date"] != date
                or type(value["amount"]) not in (int, float)
                or not isfinite(value["amount"])
                or not isinstance(value["category_id"], str)
                or not value["category_id"]
                or not isinstance(value["description"], str)
                or not value["description"]
                or "notes" not in row
                or (row["notes"] is not None and not isinstance(row["notes"], str))
            ):
                raise APIError(
                    "Transaction search data was incomplete or outside its scope.",
                    details={"fix": fix},
                )
            yield value
        offset += len(rows)
        if offset == total:
            return
