"""Validated replacement of transaction splits with confirmed desired state."""

from decimal import Decimal
from math import isfinite
from shlex import join
from typing import Any

from .exceptions import APIError, ValidationError
from .responses import complete_ids

_ALIASES = {"category_id": "categoryId", "merchant_name": "merchantName"}
_ALLOWED = {"amount", "categoryId", "merchantName", "notes"}


def _number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and isfinite(value)
    except OverflowError:
        return False


def normalize_splits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Accept documented aliases without passing unsupported input to GraphQL."""
    result = []
    for row in rows:
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            field = _ALIASES.get(key, key)
            if field not in _ALLOWED or (field in normalized and normalized[field] != value):
                raise ValidationError(
                    "Split fields are unsupported or conflicting.", field="splits-json"
                )
            normalized[field] = value
        if not _number(normalized.get("amount")):
            raise ValidationError(
                "Each split requires a finite numeric amount.", field="splits-json"
            )
        if (
            not isinstance(normalized.get("categoryId"), str)
            or not normalized["categoryId"].strip()
        ):
            raise ValidationError(
                "Each split requires a nonempty category ID.", field="splits-json"
            )
        for field in ("merchantName", "notes"):
            if field in normalized and not isinstance(normalized[field], str):
                raise ValidationError(
                    "Split merchant names and notes must be strings.", field="splits-json"
                )
        if "merchantName" in normalized and not normalized["merchantName"].strip():
            raise ValidationError("Split merchant names must not be empty.", field="splits-json")
        result.append(normalized)
    return result


def _rows(transaction: Any, transaction_id: str) -> list[dict[str, Any]]:
    if not isinstance(transaction, dict) or transaction.get("id") != transaction_id:
        raise APIError("Could not confirm the transaction split response.")
    complete_ids(transaction, "splitTransactions")
    rows: list[dict[str, Any]] = transaction["splitTransactions"]
    for row in rows:
        if not _number(row.get("amount")):
            raise APIError("Invalid split amount in transaction response.")
        if (
            not isinstance(row.get("category"), dict)
            or not isinstance(row["category"].get("id"), str)
            or not row["category"]["id"]
        ):
            raise APIError("Invalid split category in transaction response.")
        if not isinstance(row.get("merchant"), dict) or not isinstance(
            row["merchant"].get("name"), str
        ):
            raise APIError("Invalid split merchant in transaction response.")
        if "notes" not in row or (row["notes"] is not None and not isinstance(row["notes"], str)):
            raise APIError("Invalid split notes in transaction response.")
    return rows


def _row_matches(actual: dict[str, Any], desired: dict[str, Any]) -> bool:
    for key, value in desired.items():
        if key == "categoryId":
            current = actual.get("category", {}).get("id")
        elif key == "merchantName":
            merchant = actual.get("merchant")
            current = merchant.get("name") if isinstance(merchant, dict) else None
        elif key == "notes":
            if "notes" not in actual:
                return False
            current = actual["notes"] or ""
        else:
            current = actual.get(key)
        if current != value:
            return False
    return True


def matches_splits(actual: list[dict[str, Any]], desired: list[dict[str, Any]]) -> bool:
    """Match rows independent of order, retaining duplicate counts and optional fields."""
    if len(actual) != len(desired):
        return False
    # Augmenting paths avoid greedy mismatches when optional fields overlap.
    assigned: dict[int, int] = {}
    inverse: dict[int, int] = {}

    def assign(index: int) -> bool:
        pending = [index]
        previous: dict[int, int] = {}
        while pending:
            source = pending.pop()
            for candidate, row in enumerate(actual):
                if candidate in previous or not _row_matches(row, desired[source]):
                    continue
                previous[candidate] = source
                if candidate in assigned:
                    pending.append(assigned[candidate])
                    continue
                while True:
                    source = previous[candidate]
                    old = inverse.get(source)
                    assigned[candidate] = source
                    inverse[source] = candidate
                    if old is None:
                        return True
                    candidate = old
        return False

    return all(assign(index) for index in range(len(desired)))


async def replace_splits(
    client: Any, transaction_id: str, desired: list[dict[str, Any]]
) -> tuple[str, Any]:
    """Read, compare, replace once, and confirm both splits and the parent amount."""
    before = await client.get_transaction_splits(transaction_id)
    transaction: Any = (
        before.get("getTransaction")
        if isinstance(before, dict) and not before.get("errors")
        else None
    )
    rows = _rows(transaction, transaction_id)
    amount = transaction.get("amount")
    if not _number(amount):
        raise APIError("Could not read the parent transaction amount.")
    if desired and sum((Decimal(str(row["amount"])) for row in desired), Decimal(0)) != Decimal(
        str(amount)
    ):
        raise ValidationError(
            "Split amounts must add up to the parent transaction amount.",
            field="splits-json",
            details={"fix": join(["monarch", "transactions", "splits", "show", transaction_id])},
        )
    if matches_splits(rows, desired):
        return "unchanged", before

    result = await client.update_transaction_splits(
        transaction_id=transaction_id, split_data=desired
    )
    payload = (
        result.get("updateTransactionSplit")
        if isinstance(result, dict) and not result.get("errors")
        else None
    )
    fix = join(["monarch", "transactions", "splits", "show", transaction_id])
    if not isinstance(payload, dict) or payload.get("errors"):
        raise APIError(
            "Could not confirm the split update. Inspect before retrying.",
            details={"response": result, "fix": fix},
        )
    updated: Any = payload.get("transaction")
    updated_rows = _rows(updated, transaction_id)
    if updated.get("hasSplitTransactions") is not bool(desired) or not matches_splits(
        updated_rows, desired
    ):
        raise APIError("Returned splits did not match the requested state.", details={"fix": fix})
    after = await client.get_transaction_splits(transaction_id)
    current: Any = (
        after.get("getTransaction") if isinstance(after, dict) and not after.get("errors") else None
    )
    current_rows = _rows(current, transaction_id)
    if (
        not _number(current.get("amount"))
        or current.get("amount") != amount
        or not matches_splits(current_rows, desired)
    ):
        raise APIError(
            "Split update did not survive readback. Inspect before retrying.", details={"fix": fix}
        )
    return "updated", result
