"""Confirmed desired-state changes to account metadata and displayed balance."""

from math import isfinite
from shlex import join
from typing import Any

from .exceptions import APIError, NotFoundError, ValidationError
from .responses import complete_ids

_FIELDS = {
    "account_name": "displayName",
    "account_balance": "displayBalance",
    "account_type": "type",
    "account_sub_type": "subtype",
    "include_in_net_worth": "includeInNetWorth",
    "hide_from_summary_list": "hideFromList",
    "hide_transactions_from_reports": "hideTransactionsFromReports",
}


def validate_account_changes(account_id: str | None, changes: dict[str, Any]) -> None:
    if account_id is not None and not account_id.strip():
        raise ValidationError("Provide an account ID.", field="account_id")
    if "account_balance" in changes and not isfinite(changes["account_balance"]):
        raise ValidationError("Provide a finite account balance.", field="balance")
    for key, flag in (
        ("account_name", "name"),
        ("account_type", "type"),
        ("account_sub_type", "subtype"),
    ):
        if key in changes and not changes[key].strip():
            raise ValidationError("Provide a nonempty value.", field=flag)


def _matches(account: Any, account_id: str, changes: dict[str, Any]) -> bool:
    if not isinstance(account, dict) or account.get("id") != account_id:
        return False
    for key, desired in changes.items():
        field = _FIELDS[key]
        if field not in account:
            return False
        actual = account[field]
        if key in {"account_type", "account_sub_type"}:
            actual = actual.get("name") if isinstance(actual, dict) else None
        if isinstance(actual, bool) != isinstance(desired, bool) or actual != desired:
            return False
    return True


async def change_account(client: Any, account_id: str, changes: dict[str, Any]) -> tuple[str, Any]:
    before = await client.get_accounts()
    ids = complete_ids(before, "accounts")
    if account_id not in ids:
        raise NotFoundError(
            "Account was not found.", resource_type="account", resource_id=account_id
        )
    current = next(row for row in before["accounts"] if row["id"] == account_id)
    if _matches(current, account_id, changes):
        return "unchanged", {"updateAccount": {"account": current, "errors": []}}
    result = await client.update_account(account_id=account_id, **changes)
    payload = (
        result.get("updateAccount")
        if isinstance(result, dict) and not result.get("errors")
        else None
    )
    if (
        not isinstance(payload, dict)
        or payload.get("errors")
        or not _matches(payload.get("account"), account_id, changes)
    ):
        raise APIError(
            "Could not confirm the account update. Inspect before retrying.",
            details={"response": result, "fix": join(["monarch", "accounts", "show", account_id])},
        )
    return "updated", result
