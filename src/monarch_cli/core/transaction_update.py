"""Compatibility path for explicit zero amounts omitted by the SDK."""

from datetime import date
from math import isfinite
from shlex import join
from typing import Any

from graphql import parse

from .exceptions import APIError, ValidationError

_FIELDS = {
    "category_id": "category",
    "merchant_name": "name",
    "goal_id": "goalId",
    "amount": "amount",
    "date": "date",
    "hide_from_reports": "hideFromReports",
    "needs_review": "needsReview",
    "notes": "notes",
}


def validate_transaction_changes(changes: dict[str, Any]) -> None:
    """Reject locally invalid setter values before authentication."""
    if "amount" in changes and not isfinite(changes["amount"]):
        raise ValidationError("Provide a finite transaction amount.", field="amount")
    for field, flag in (("category_id", "category"), ("merchant_name", "description")):
        if field in changes and not str(changes[field]).strip():
            raise ValidationError("Provide a nonempty value.", field=flag)
    if "date" in changes:
        try:
            if date.fromisoformat(changes["date"]).isoformat() != changes["date"]:
                raise ValueError
        except ValueError as exc:
            raise ValidationError("Provide a date in YYYY-MM-DD format.", field="date") from exc


async def update_zero_amount(client: Any, transaction_id: str, changes: dict[str, Any]) -> Any:
    """Use the SDK's mutation schema while retaining numeric zero in its input."""
    query = parse("""
        mutation Web_TransactionDrawerUpdateTransaction($input: UpdateTransactionMutationInput!) {
            updateTransaction(input: $input) {
                transaction {
                    id amount date hideFromReports needsReview notes
                    category { id } merchant { name } goal { id }
                }
                errors { message code }
            }
        }
    """)
    values = {"id": transaction_id}
    values.update({_FIELDS[key]: value for key, value in changes.items()})
    result = await client.gql_call(
        operation="Web_TransactionDrawerUpdateTransaction",
        graphql_query=query,
        variables={"input": values},
    )
    payload = result.get("updateTransaction") if isinstance(result, dict) else None
    transaction = payload.get("transaction") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("errors")
        or not isinstance(transaction, dict)
        or str(transaction.get("id")) != transaction_id
        or isinstance(transaction.get("amount"), bool)
        or transaction.get("amount") != 0
    ):
        raise APIError(
            "Could not confirm the zero-amount update. Inspect the transaction before retrying.",
            details={"response": result, "fix": f"monarch transactions show {transaction_id}"},
        )
    return result


def checked_current_transaction(raw: Any, transaction_id: str) -> dict[str, Any]:
    """Only canonical, exact-target, finite current data permits a write."""
    current = raw.get("getTransaction") if isinstance(raw, dict) and not raw.get("errors") else None
    if (
        not isinstance(current, dict)
        or current.get("id") != transaction_id
        or type(current.get("amount")) not in (int, float)
        or not isfinite(current["amount"])
    ):
        raise APIError(
            "Could not read the exact transaction before updating it.",
            details={"fix": join(["monarch", "transactions", "show", transaction_id])},
        )
    return current


def confirm_transaction_update(result: Any, transaction_id: str, changes: dict[str, Any]) -> None:
    """Reject wrapper success flags, payload failures, and silently ignored changes."""
    payload = (
        result.get("updateTransaction")
        if isinstance(result, dict) and not result.get("errors")
        else None
    )
    if (
        not isinstance(payload, dict)
        or payload.get("errors")
        or not matches_changes(payload.get("transaction"), transaction_id, changes)
    ):
        raise APIError(
            "Could not confirm the transaction update. Inspect before retrying.",
            details={
                "response": result,
                "fix": join(["monarch", "transactions", "show", transaction_id]),
            },
        )


def matches_changes(transaction: Any, transaction_id: str, changes: dict[str, Any]) -> bool:
    """Only observed fields from the exact target can establish a no-op."""
    if not isinstance(transaction, dict) or str(transaction.get("id")) != transaction_id:
        return False
    for key, desired in changes.items():
        field = _FIELDS[key]
        if key in {"category_id", "merchant_name", "goal_id"}:
            field = {"category_id": "category", "merchant_name": "merchant", "goal_id": "goal"}[key]
            if field not in transaction:
                return False
            nested = transaction[field]
            if key == "goal_id" and nested is None and desired == "":
                continue
            if not isinstance(nested, dict):
                return False
            subfield = "name" if key == "merchant_name" else "id"
            if subfield not in nested:
                return False
            actual = nested[subfield]
        else:
            if field not in transaction:
                return False
            actual = transaction[field]
            if key == "notes" and actual is None and desired == "":
                continue
        if isinstance(actual, bool) != isinstance(desired, bool):
            return False
        if actual != desired:
            return False
    return True


def confirm_created_fields(
    transaction: dict[str, Any], transaction_id: str, *, changes: dict[str, Any], account: str
) -> None:
    """Reject contradictory observed fields while retaining native manual-row fallbacks."""
    known = {}
    for key, value in changes.items():
        field = {"merchant_name": "merchant", "category_id": "category"}.get(key, _FIELDS[key])
        if field in transaction and transaction[field] is not None:
            known[key] = value
    current_account = transaction.get("account")
    wrong_account = current_account is not None and (
        not isinstance(current_account, dict) or current_account.get("id") not in (None, account)
    )
    if wrong_account or not matches_changes(transaction, transaction_id, known):
        raise APIError(
            "Created transaction readback contradicts the request. Inspect before retrying.",
            details={"fix": join(["monarch", "transactions", "show", transaction_id])},
        )
