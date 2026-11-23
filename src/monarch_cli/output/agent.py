"""Compact AXI views over unchanged internal and explicit JSON schemas."""

from __future__ import annotations

import shlex
from enum import Enum
from typing import Any

import click

from ..core.agent_context import command_path as command_path
from ..core.agent_context import options
from ..core.exceptions import ValidationError

TEXT_LIMIT = 1000


def _field(row: Any, path: str) -> Any:
    def follow(value: Any, keys: list[str]) -> Any:
        if not keys:
            return value
        if isinstance(value, list):
            return [follow(item, keys) for item in value]
        key, *remaining = keys
        if not isinstance(value, dict) or key not in value:
            raise ValidationError(
                f"Unknown field: {path}",
                details={
                    "available_fields": list(row) if isinstance(row, dict) else [],
                    "output_selection": True,
                },
            )
        return follow(value[key], remaining)

    return follow(row, path.split("."))


def project(data: Any) -> Any:
    """Explicit field requests may intentionally change JSON as well as TOON output."""
    requested = options().get("fields")
    if not requested:
        return data
    fields = requested.split(",")
    if any(not field.strip() for field in fields):
        raise ValidationError(
            "--fields requires nonempty comma-separated field paths",
            details={"output_selection": True},
        )
    fields = list(dict.fromkeys(field.strip() for field in fields))
    if isinstance(data, list):
        return [{field: _field(row, field) for field in fields} for row in data]
    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            return {**data, "results": project(data["results"])}
        return {field: _field(data, field) for field in fields}
    raise ValidationError(
        "--fields requires object or collection output", details={"output_selection": True}
    )


def _receipt_row(row: dict[str, Any]) -> dict[str, Any]:
    orders = row.get("orders")
    names: list[str] = []
    known = isinstance(orders, list)
    linked = count = 0
    for order in orders if isinstance(orders, list) else []:
        if not isinstance(order, dict):
            known = False
            continue
        name = order.get("merchantName")
        if isinstance(name, str) and name and name not in names:
            names.append(name)
        transactions = order.get("retailTransactions")
        if not isinstance(transactions, list):
            known = False
            continue
        for transaction in transactions:
            if not isinstance(transaction, dict) or "transaction" not in transaction:
                known = False
                continue
            target = transaction["transaction"]
            count += 1
            if target is not None:
                if (
                    not isinstance(target, dict)
                    or not isinstance(target.get("id"), str)
                    or not target["id"]
                ):
                    known = False
                else:
                    linked += 1
    merchant = names[0] if names else None
    if len(names) > 1:
        merchant = f"{merchant} (+{len(names) - 1})"
    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "merchant": merchant,
        "matches": f"{linked}/{count}" if known else None,
    }


def _compact(row: dict[str, Any], path: str) -> dict[str, Any]:
    if path == "receipts inbox":
        return _receipt_row(row)
    if path == "cashflow detail" and isinstance(row.get("groupBy"), dict):
        group = next(iter(row["groupBy"].values()), {}) or {}
        summary = row.get("summary") or {}
        amounts = (
            {"income": summary.get("sumIncome"), "expense": summary.get("sumExpense")}
            if "merchant" in row["groupBy"]
            else {"amount": summary.get("sum")}
        )
        return {"id": group.get("id"), "name": group.get("name"), **amounts}
    if "recentBalances" in row:
        return {"id": row.get("id"), "recentBalances": row["recentBalances"]}
    if path == "cashflow recurring" and isinstance(row.get("stream"), dict):
        stream = row["stream"]
        return {
            "id": stream.get("id"),
            "merchant": (stream.get("merchant") or {}).get("name"),
            "date": row.get("date"),
            "amount": row.get("amount"),
        }
    if path == "cashflow credit-history" and "reportedDate" in row:
        return {
            "date": row["reportedDate"],
            "score": row.get("score"),
            "user_id": (row.get("user") or {}).get("id"),
        }
    if path == "cashflow institutions" and isinstance(row.get("institution"), dict):
        return {
            "id": row.get("id"),
            "name": row["institution"].get("name"),
            "status": row["institution"].get("status"),
            "update_required": row.get("updateRequired"),
        }
    if path == "accounts holdings" and isinstance(row.get("node"), dict):
        node = row["node"]
        security = node.get("security") or {}
        return {
            "id": node.get("id"),
            "security": security.get("ticker") or security.get("name"),
            "quantity": node.get("quantity"),
            "value": node.get("totalValue"),
        }
    if path == "report list":
        view = row.get("reportView") or {}
        return {
            "id": row.get("id"),
            "displayName": row.get("displayName"),
            "type": view.get("analysisScope", "filters_only"),
        }
    if path in {"transactions list", "receipts missing"}:
        fields = ["id", "date", "description", "amount"]
    elif path == "accounts list":
        fields = ["id", "name", "balance", "is_active"]
    elif path == "investments holdings":
        fields = (
            ["account_id", "ticker", "quantity", "total_value"]
            if "account_id" in row
            else ["ticker", "name", "quantity", "total_value"]
        )
    elif path == "investments securities":
        fields = ["id", "ticker", "name", "currentPrice"]
    elif path in {"categories", "categories list"}:
        fields = ["id", "name", "group"]
    elif path == "result list":
        fields = ["id", "saved_at", "size_bytes"]
    elif path == "transactions tags list":
        fields = ["id", "name", "color", "transactionCount"]
    else:
        fields = [
            key
            for key in (
                "id",
                "name",
                "displayName",
                "filename",
                "symbol",
                "status",
                "date",
                "month",
                "amount",
                "balance",
                "signedBalance",
                "accountType",
                "ticker",
                "quantity",
                "totalValue",
                "type",
            )
            if key in row
        ][:4]
        if not fields:
            fields = list(row)[:4]
    return {key: row[key] for key in fields if key in row}


def _truncate(value: Any, changes: list[str], path: str = "") -> Any:
    if isinstance(value, str) and len(value) > TEXT_LIMIT:
        changes.append(path)
        return value[:TEXT_LIMIT] + f"... (truncated, {len(value)} chars total)"
    if isinstance(value, dict):
        return {
            key: _truncate(item, changes, f"{path}.{key}".strip(".")) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_truncate(item, changes, f"{path}[{index}]") for index, item in enumerate(value)]
    return value


def invocation(*, overrides: dict[str, Any] | None = None, full: bool = False) -> str:
    """Rebuild a copyable command while keeping ID arguments and filter flags."""
    context = click.get_current_context(silent=True)
    chain = []
    while context:
        chain.append(context)
        context = context.parent
    arguments: list[str] = ["monarch"]
    for ctx in reversed(chain):
        if ctx.parent and ctx.info_name:
            arguments.append(ctx.info_name)
        for param in ctx.command.params:
            name = param.name or ""
            value = (overrides or {}).get(name, ctx.params.get(name))
            if isinstance(param, click.Argument) and value is not None:
                arguments.extend(str(v) for v in value) if isinstance(
                    value, tuple
                ) else arguments.append(str(value))
            elif isinstance(param, click.Option) and value is not None and param.expose_value:
                if name in {
                    "version",
                    "json_output",
                    "quiet",
                    "verbose",
                    "debug",
                    "no_color",
                    "format",
                }:
                    continue
                if isinstance(value, bool):
                    if value:
                        arguments.append(param.opts[-1])
                    elif param.secondary_opts and param.default is not False:
                        arguments.append(param.secondary_opts[-1])
                else:
                    for item in value if param.multiple else [value]:
                        arguments.extend(
                            [param.opts[-1], str(item.value if isinstance(item, Enum) else item)]
                        )
    if full:
        arguments.append("--full")
    return shlex.join(arguments)


def present(data: Any, *, total: int | None = None) -> Any:
    """Render bounded collections, preserving backend totals and safe full-result access."""
    from ..core.capabilities import is_mutating
    from ..core.exceptions import APIError

    state = options()
    path = command_path()
    context = click.get_current_context(silent=True)
    params = context.params if context else {}
    original = data
    expected = {
        "accounts history": ("snapshots", "transactions.results"),
        "accounts holdings": ("portfolio.aggregateHoldings.edges",),
        "accounts recent-balances": ("accounts",),
        "accounts snapshots": ("snapshotsByAccountType", "accountTypes"),
        "accounts aggregate-snapshots": ("aggregateSnapshots",),
        "cashflow detail": ("byCategory", "byCategoryGroup", "byMerchant", "summary"),
        "cashflow recurring": ("recurringTransactionItems",),
        "cashflow institutions": ("credentials", "accounts"),
    }
    for field in expected.get(path, ()):
        value = data
        for key in field.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if not isinstance(value, list):
            raise APIError(f"Monarch response is missing a valid {field} collection")
    data = project(data)
    if data is None or isinstance(data, dict) and not data:
        return {"status": "empty", "count": 0, "message": f"No data returned by {path}."}
    full = bool(state.get("full"))
    compact = not (
        full
        or state.get("fields")
        or params.get("raw")
        or is_mutating(path)
        or "show" in path.split()
        or path.startswith("auth ")
    )
    hints: list[str] = []
    cached_id: str | None = None

    def full_hint() -> str:
        nonlocal cached_id
        if is_mutating(path) and not params.get("dry_run"):
            from ..core.result_cache import save_result

            if cached_id is None:
                try:
                    cached_id = save_result(original)
                except (OSError, APIError) as exc:
                    from .error_help import _inspection

                    raise APIError(
                        "The operation may have completed, but full output could not be saved. "
                        "Inspect before retrying.",
                        details={"fix": _inspection(path, context), "cause": str(exc)},
                    ) from exc
            return f"monarch result show {cached_id} --full"
        return invocation(full=True)

    def collection(
        records: list[Any], label: str, meta: dict[str, Any] | None = None, root: bool = False
    ) -> dict[str, Any]:
        meta = meta or {}
        known = (
            total if root and total is not None else meta.get("total_count", meta.get("totalCount"))
        )
        paginated = root and path in {
            "transactions list",
            "receipts missing",
            "investments securities",
        }
        if known is None and not paginated and path != "api":
            known = len(records)
        if known is not None and (type(known) is not int or known < len(records)):
            raise APIError("Invalid collection total in Monarch response")
        offset = meta.get("offset", params.get("offset", 0))
        limit = params.get("limit", 100)
        shown = records if full else records[:limit]
        items = [
            walk(_compact(row, path) if compact and isinstance(row, dict) else row, label)
            for row in shown
        ]
        result = {
            key: walk(value, f"{label}.{key}".strip("."))
            for key, value in meta.items()
            if key != "results"
        }
        result.update(
            {
                "count": len(shown),
                "total_count": known,
                "results" if "results" in meta else "items": items,
            }
        )
        if known is None:
            result["total_count_available"] = False
            result["message"] = "Total matching count was not provided by this response."
        if not records:
            suffix = " on this page" if known is not None and known > 0 else ""
            result["message"] = f"No {path} {label} results{suffix}".replace("  ", " ")
        if len(shown) < len(records):
            if "limit" in params and "offset" not in params:
                hints.append(invocation(overrides={"limit": len(records)}))
            else:
                hints.append(full_hint())
        if known is not None and offset + len(records) < known:
            if path == "accounts history" and label == "transactions":
                hints.append(
                    shlex.join(
                        [
                            "monarch",
                            "transactions",
                            "list",
                            "--account",
                            str(params["account_id"]),
                            "--offset",
                            str(len(records)),
                            "--limit",
                            "100",
                        ]
                    )
                )
            elif "offset" in params:
                hints.append(invocation(overrides={"offset": offset + len(records)}))
        if (
            path == "transactions tags list"
            and label == "householdTransactionTags"
            and records
            and isinstance(records[0], dict)
            and records[0].get("id")
        ):
            hints.append(
                shlex.join(["monarch", "transactions", "list", "--tag", str(records[0]["id"])])
            )
        if root and records and isinstance(records[0], dict):
            identity = records[0].get("id")
            if path in {"categories", "categories list"} and identity:
                hints.append(
                    shlex.join(["monarch", "transactions", "list", "--category", str(identity)])
                )
            if path in {"budgets", "budgets list"}:
                hints.append("monarch categories list")
            group = path.rsplit(" ", 1)[0]
            if path in {"receipts list", "receipts missing"}:
                identity = params.get("transaction_id") if path == "receipts list" else identity
                group = "transactions"
            command = context.find_root().command if context else None
            for word in group.split():
                command = command.commands.get(word) if isinstance(command, click.Group) else None
            if identity:
                for detail in ("show", "history"):
                    if isinstance(command, click.Group) and detail in command.commands:
                        hints.append(shlex.join(["monarch", *group.split(), detail, str(identity)]))
                        break
        if root and not records and path == "report list":
            hints.append('monarch report create --name "New report" --dry-run')
        return result

    def walk(value: Any, label: str = "", root: bool = False) -> Any:
        if isinstance(value, list):
            if (
                not root
                and not state.get("fields")
                and value
                and all(not isinstance(item, (dict, list)) for item in value)
                and (full or len(value) <= params.get("limit", 100))
            ):
                return value  # Small vectors/config values keep TOON's dense array header.
            return collection(value, label, root=root)
        if isinstance(value, dict):
            if isinstance(value.get("results"), list):
                return collection(value["results"], label, value, root=root)
            return {
                key: item if key == "help" else walk(item, f"{label}.{key}".strip("."))
                for key, item in value.items()
                if full or state.get("fields") or key != "__typename"
            }
        return value

    # The capabilities reference is a complete contract, rather than a data collection view.
    data = data if path == "capabilities" else walk(data, root=True)
    changes: list[str] = []
    if not full:
        data = _truncate(data, changes)
    if changes:
        hints.append(full_hint())
    if hints and isinstance(data, dict):
        data = {**data, "help": list(dict.fromkeys([*data.get("help", []), *hints]))}
    return data
