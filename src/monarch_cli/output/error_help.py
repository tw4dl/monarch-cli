"""Actionable CLI repairs; uncertain or completed writes are never replayed."""

import shlex

import click

from ..core.capabilities import is_mutating
from ..core.exceptions import MonarchCLIError
from .agent import command_path, invocation


def _inspection(path: str, context: click.Context | None) -> str:
    values = context.params if context else {}
    if values.get("transaction_id"):
        if path.startswith("transactions splits "):
            return shlex.join(
                ["monarch", "transactions", "splits", "show", values["transaction_id"]]
            )
        return shlex.join(["monarch", "transactions", "show", values["transaction_id"]])
    if values.get("receipt_id"):
        return shlex.join(["monarch", "receipts", "show", values["receipt_id"]])
    if values.get("report_id"):
        return shlex.join(["monarch", "report", "show", values["report_id"]])
    if path.startswith("investments holding ") and values.get("account"):
        return shlex.join(
            [
                "monarch",
                "investments",
                "holdings",
                "--account",
                values["account"],
                "--detailed",
                "--raw",
                "--full",
            ]
        )
    if path in {"transactions create", "transactions upsert"} and values.get("account"):
        args = ["monarch", "transactions", "list", "--account", values["account"]]
        if values.get("date_value"):
            args.extend(["--start", values["date_value"], "--end", values["date_value"]])
        return shlex.join(args)
    if values.get("account_id"):
        if path == "accounts delete":
            return "monarch accounts list"
        detail = "history" if path == "accounts upload-history" else "show"
        return shlex.join(["monarch", "accounts", detail, values["account_id"]])
    if path == "accounts refresh":
        args = ["monarch", "accounts", "refresh-status"]
        for account in values.get("account") or []:
            args.extend(["--account", account])
        if values.get("active_linked"):
            args.append("--active-linked")
        return shlex.join(args)
    if path == "budgets flex-rollover":
        return "monarch budgets settings"
    if path.startswith("budgets "):
        from ..core.budget_result import budget_inspection

        return budget_inspection(values.get("start") or values.get("start_month"))
    parent = context.parent.command if context and context.parent else None
    if isinstance(parent, click.Group):
        for name in ["list", "status", "summary"]:
            if name in parent.commands:
                args = ["monarch", *path.split()[:-1], name]
                if path.startswith("budgets ") and values.get("start"):
                    args.extend(["--start", values["start"]])
                return shlex.join(args)
    return "monarch auth ping --json"


def suggestions(error: MonarchCLIError) -> list[str]:
    path = command_path()
    context = click.get_current_context(silent=True)
    if error.details.get("output_selection") and is_mutating(path):
        return [_inspection(path, context)]
    fields = error.details.get("available_fields")
    if isinstance(fields, list) and fields:
        if is_mutating(path):
            return [_inspection(path, context)]
        return [shlex.join([*shlex.split(invocation()), "--fields", str(fields[0])])]
    fix = error.details.get("fix")
    if isinstance(fix, str):
        return [fix]
    if "--yes" in error.message:
        if context and any(p.name == "dry_run" for p in context.command.params):
            return [invocation(overrides={"dry_run": True, "yes": False})]
        return [_inspection(path, context)]
    if error.code.value in {"UNKNOWN", "NETWORK_ERROR", "API_ERROR"}:
        if is_mutating(path):
            return [_inspection(path, context)]
        if error.code.value in {"NETWORK_ERROR", "API_ERROR"}:
            return ["monarch auth ping --json"]
        arguments = shlex.split(invocation())
        return [shlex.join([arguments[0], "--debug", *arguments[1:]])]
    if error.code.value in {"AUTH_REQUIRED", "AUTH_EXPIRED", "AUTH_FAILED"}:
        from ..commands.auth import LOGIN_COMMAND

        return [LOGIN_COMMAND]
    if error.code.value == "NOT_FOUND":
        if path.startswith("investments "):
            return [_inspection(path, context)]
        if path.startswith("receipts "):
            return ["monarch receipts inbox"]
        return [shlex.join(["monarch", path.split()[0] if path else "accounts", "list"])]
    if error.code.value == "INVALID_INPUT":
        from ..core.help_reference import repair_example

        if context:
            field = str(error.details.get("field", "")).lstrip("-").replace("-", "_")
            invalid = next(
                (
                    p
                    for p in context.command.params
                    if field
                    and (
                        p.name == field
                        or isinstance(p, click.Option)
                        and any(flag.lstrip("-").replace("-", "_") == field for flag in p.opts)
                    )
                ),
                None,
            )
            return [repair_example(context, invalid)]
    return ["monarch auth ping --json"]
