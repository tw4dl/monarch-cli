"""Check the budget payloads selected by the installed SDK."""

from calendar import monthrange
from datetime import date
from math import isfinite
from shlex import join
from typing import Any

from graphql import parse

from .exceptions import APIError, ValidationError

_ROLLOVER_SETTINGS_QUERY = parse(
    "query Web_GetFlexibleGroupRolloverSettings { "
    "budgetSystem flexExpenseRolloverPeriod { id startMonth startingBalance } }"
)


async def read_rollover_settings(client: Any) -> dict[str, Any]:
    """Use the native UI's independent settings query, without inferring missing fields."""
    data = await client.gql_call(
        operation="Web_GetFlexibleGroupRolloverSettings",
        graphql_query=_ROLLOVER_SETTINGS_QUERY,
        variables={},
    )
    if (
        not isinstance(data, dict)
        or data.get("errors")
        or not isinstance(data.get("budgetSystem"), str)
        or "flexExpenseRolloverPeriod" not in data
        or not _valid_period(data["flexExpenseRolloverPeriod"])
    ):
        raise APIError("Missing or invalid native budget settings.")
    return data


def _valid_period(period: Any) -> bool:
    return period is None or (
        isinstance(period, dict)
        and isinstance(period.get("id"), str)
        and bool(period["id"])
        and isinstance(period.get("startMonth"), str)
        and type(period.get("startingBalance")) in (int, float)
        and isfinite(period["startingBalance"])
    )


async def verify_rollover_settings(
    client: Any, expected: str, start: str, enabled: bool, balance: float
) -> None:
    """The native UI defines enabled as a non-null rollover period."""
    try:
        data = await read_rollover_settings(client)
    except APIError as exc:
        raise APIError(
            "Could not read back rollover settings. Inspect before retrying.",
            details={"fix": "monarch budgets settings"},
        ) from exc
    period = data["flexExpenseRolloverPeriod"]
    matches = (
        period is None
        if not enabled
        else (
            isinstance(period, dict)
            and period["startMonth"] == start
            and period["startingBalance"] == balance
        )
    )
    if data["budgetSystem"] != expected or not matches:
        raise APIError(
            "Rollover settings differ from the request. Inspect before retrying.",
            details={"fix": "monarch budgets settings"},
        )


def budget_inspection(start: str | None) -> str:
    """Inspect native bucket/group data within the requested calendar month."""
    arguments = ["monarch", "budgets", "list", "--raw"]
    if start:
        try:
            day = date.fromisoformat(start)
        except ValueError:
            return join(arguments)
        end = day.replace(day=monthrange(day.year, day.month)[1]).isoformat()
        arguments.extend(["--start", start, "--end", end])
    return join(arguments)


def check_budget_input(
    start: str | None,
    amount: float | None = None,
    date_field: str = "start",
    amount_field: str = "amount",
) -> None:
    """Reject malformed local values before loading credentials or calling the SDK."""
    if amount is not None and not isfinite(amount):
        raise ValidationError("Provide a finite budget amount.", field=amount_field)
    if start is not None:
        try:
            if date.fromisoformat(start).isoformat() != start:
                raise ValueError
        except ValueError as exc:
            raise ValidationError("Provide a date in YYYY-MM-DD format.", field=date_field) from exc


def checked_budget_result(
    data: Any,
    field: str,
    amount: float | None = None,
    *,
    period_start: str | None = None,
    period_balance: float | None = None,
    inspection_start: str | None = None,
    inspection_command: str | None = None,
) -> None:
    """Reject absent, rejected, or mismatched budget mutation payloads."""
    payload: Any = data.get(field) if isinstance(data, dict) and not data.get("errors") else None
    valid = isinstance(payload, dict) and not payload.get("errors")
    if valid and amount is not None:
        item = payload.get("budgetItem")
        valid = (
            isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and bool(item["id"])
            and not isinstance(item.get("budgetAmount"), bool)
            and item.get("budgetAmount") == amount
        )
    elif valid and field == "resetBudget":
        valid = "errors" in payload and payload["errors"] in (None, [])
    elif valid and field == "updateBudgetSettings":
        period = payload.get("budgetRolloverPeriod")
        valid = "budgetRolloverPeriod" in payload and (
            period is None
            or (
                isinstance(period, dict)
                and isinstance(period.get("id"), str)
                and bool(period["id"])
                and isinstance(period.get("startMonth"), str)
                and type(period.get("startingBalance")) in (int, float)
                and isfinite(period["startingBalance"])
            )
        )
        if period_start is not None:
            valid = (
                valid
                and isinstance(period, dict)
                and period.get("startMonth") == period_start
                and period.get("startingBalance") == period_balance
            )
    if not valid:
        raise APIError(
            "Could not confirm the budget change. Inspect the budget before retrying.",
            details={
                "response": data,
                "fix": inspection_command or budget_inspection(inspection_start),
            },
        )
