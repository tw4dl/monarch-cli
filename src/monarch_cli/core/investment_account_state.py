"""Proof required before treating investment-account creation as a no-op."""

from decimal import Decimal, InvalidOperation
from typing import Any

from .exceptions import APIError
from .responses import records_at


def settings_match(account: dict[str, Any], subtype: str, in_net_worth: bool) -> bool:
    native_subtype = account.get("subtype")
    return (
        account.get("isManual") is True
        and account.get("manualInvestmentsTrackingMethod") == "holdings"
        and account.get("includeInNetWorth") is in_net_worth
        and account.get("includeBalanceInNetWorth") is in_net_worth
        and isinstance(native_subtype, dict)
        and native_subtype.get("name") == subtype
    )


def holdings_match(data: Any, requested: list[dict[str, Any]]) -> bool:
    observed: dict[str, Decimal] = {}
    ids: set[str] = set()
    for edge in records_at(data, "portfolio.aggregateHoldings.edges"):
        node = edge.get("node")
        security = node.get("security") if isinstance(node, dict) else None
        if (
            not isinstance(security, dict)
            or not isinstance(security.get("id"), str)
            or not security["id"]
        ):
            raise APIError("Cannot verify existing investment account security IDs.")
        security_id = security["id"]
        for holding in records_at(node, "holdings"):
            identity = holding.get("id")
            quantity = holding.get("quantity")
            if not isinstance(identity, str) or not identity or identity in ids:
                raise APIError("Cannot verify existing investment account holding IDs.")
            ids.add(identity)
            if (
                holding.get("isManual") is not True
                or quantity is None
                or isinstance(quantity, bool)
            ):
                return False
            try:
                value = Decimal(str(quantity))
            except InvalidOperation:
                return False
            if not value.is_finite() or security_id in observed:
                return False
            observed[security_id] = value
    expected = {row["securityId"]: Decimal(str(row["quantity"])) for row in requested}
    return observed == expected
