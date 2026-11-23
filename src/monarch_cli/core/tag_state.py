"""Exact transaction tag state: validated reads, successful no-ops, one verified write."""

import shlex
from typing import Any

from .exceptions import APIError, NotFoundError, ValidationError
from .responses import complete_ids


def checked_tag_ids(values: list[str]) -> list[str]:
    if any(not value.strip() for value in values):
        raise ValidationError("Tag IDs must not be empty", field="tag")
    return list(dict.fromkeys(values))


def _tags(transaction: Any, transaction_id: str) -> list[str]:
    if not isinstance(transaction, dict) or transaction.get("id") != transaction_id:
        raise APIError("Tag response did not identify the requested transaction")
    complete_ids(transaction, "tags")
    return [row["id"] for row in transaction["tags"]]


async def change_tags(
    client: Any, transaction_id: str, *, mode: str, values: list[str]
) -> dict[str, Any]:
    if mode not in {"set", "remove", "clear"}:
        raise ValidationError("Unknown tag operation")
    values = checked_tag_ids(values)
    raw = await client.get_transaction_details(transaction_id=transaction_id, redirect_posted=False)
    if not isinstance(raw, dict) or raw.get("errors") or "getTransaction" not in raw:
        raise APIError("Cannot read the current transaction tags")
    if raw["getTransaction"] is None:
        raise NotFoundError("Transaction not found", resource_id=transaction_id)
    before = _tags(raw["getTransaction"], transaction_id)
    desired = (
        values
        if mode == "set"
        else [tag for tag in before if tag not in values]
        if mode == "remove"
        else []
    )
    removed = [tag for tag in before if tag not in desired]
    if set(before) == set(desired):
        return {
            "status": "unchanged",
            "tag_ids": before,
            "removed_tag_ids": [],
            "message": "Tag state already matches; no write needed.",
        }
    result = await client.set_transaction_tags(transaction_id=transaction_id, tag_ids=desired)
    payload = result.get("setTransactionTags") if isinstance(result, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("errors")
        or set(_tags(payload.get("transaction"), transaction_id)) != set(desired)
    ):
        raise APIError(
            "Monarch did not confirm the requested tag state; inspect before retrying.",
            details={"fix": shlex.join(["monarch", "transactions", "show", transaction_id])},
        )
    return {"status": "updated", "tag_ids": desired, "removed_tag_ids": removed, "result": result}
