"""Compare full native report state, including filters omitted from create input."""

from typing import Any

from .report_config import (
    BOOL_FILTERS,
    DATE_FILTERS,
    LIST_FILTERS,
    NUMBER_FILTERS,
    STRING_FILTERS,
    VIEW_FIELDS,
)


def native_filter_name(key: str) -> str:
    if key.startswith("exclude") and key in LIST_FILTERS:
        return "excluded" + key[7:]
    return {"search": "searchQuery", "transactionVisibility": "hiddenFromReports"}.get(key, key)


def report_matches(report: dict[str, Any], spec: dict[str, Any]) -> bool:
    filters = report.get("transactionFilterSet")
    view = report.get("reportView")
    if not isinstance(filters, dict) or not isinstance(view, dict):
        return False
    keys = (
        BOOL_FILTERS
        | DATE_FILTERS
        | LIST_FILTERS
        | NUMBER_FILTERS
        | STRING_FILTERS
        | {"timeframePeriod"}
    )
    requested = spec["transactionFilters"]
    for key in keys:
        native = native_filter_name(key)
        if native not in filters:
            return False  # An incomplete response cannot prove equivalence.
        actual = filters[native]
        expected = requested.get(key)
        if key in LIST_FILTERS:
            if actual is None:
                actual = []
            elif isinstance(actual, list) and all(
                isinstance(row, dict) and isinstance(row.get("id"), str) for row in actual
            ):
                actual = [row["id"] for row in actual]
            else:
                return False
            actual, expected = sorted(actual), sorted(expected or [])
        elif key == "transactionVisibility":
            expected = {
                "non_hidden_transactions_only": False,
                "hidden_transactions_only": True,
                "all_transactions": None,
            }.get(expected)
        elif key in {"tagMatchMode", "excludeTagMatchMode"}:
            expected = expected if expected is not None else "any"
        elif key == "needsReviewByUser" and isinstance(actual, dict):
            if not isinstance(actual.get("id"), str) or not actual["id"]:
                return False
            actual = actual.get("id")
        if actual != expected or isinstance(actual, bool) != isinstance(expected, bool):
            return False
    known = {native_filter_name(key) for key in keys} | {"id", "displayName"}
    readonly = {"systemCategories", "systemCategoryGroups", "ownershipSet", "businessEntitySet"}
    if not readonly <= filters.keys():
        return False
    if any(value is not None and value != [] for key, value in filters.items() if key not in known):
        return False
    expected_view = spec["reportView"]
    if not view.keys() >= VIEW_FIELDS:
        return False
    for key in VIEW_FIELDS:
        actual, expected = view[key], expected_view.get(key)
        if key == "chartCalculation":
            default = (
                "difference"
                if expected_view.get("chartType") == "bar"
                and expected_view.get("chartLayout") != "horizontal"
                else "sum"
            )
            actual = default if actual is None else actual
            expected = default if expected is None else expected
        if key == "dimensions":
            if actual is not None and (
                not isinstance(actual, list) or any(not isinstance(item, str) for item in actual)
            ):
                return False
            actual, expected = sorted(actual or []), sorted(expected or [])
        if actual != expected:
            return False
    return True
