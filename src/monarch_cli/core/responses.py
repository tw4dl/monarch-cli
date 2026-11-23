"""Validate collection shape before deriving counts or claiming absence."""

from typing import Any, cast

from .exceptions import APIError


def records_at(raw: Any, path: str) -> list[dict[str, Any]]:
    value = raw
    if not isinstance(raw, dict) or raw.get("errors"):
        raise APIError(f"Invalid {path} response")
    for key in path.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise APIError(f"Missing or invalid {path} collection")
    return cast(list[dict[str, Any]], value)


def complete_ids(raw: Any, field: str) -> set[str]:
    rows = records_at(raw, field)
    if any(not isinstance(row.get("id"), str) or not row["id"] for row in rows):
        raise APIError(f"Invalid {field} record IDs")
    ids = {row["id"] for row in rows}
    if len(ids) != len(rows):
        raise APIError(f"Duplicate {field} IDs in response")
    return ids


def transaction_page(raw: Any) -> tuple[list[dict[str, Any]], int]:
    rows = records_at(raw, "allTransactions.results")
    total = raw["allTransactions"].get("totalCount")
    if type(total) is not int or total < len(rows):
        raise APIError("Missing or invalid transaction total count")
    return rows, total
