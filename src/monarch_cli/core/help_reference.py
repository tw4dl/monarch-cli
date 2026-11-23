"""Reviewed example invocations and consistent parameter documentation."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

import click

# Placeholders carry the exact argument/flag shape; users replace IDs and file paths.
BASES = {
    "result list": "",
    "result show": "0123456789abcdef0123456789abcdef",
    "api": "docs",
    "capabilities": "",
    "auth login": "--email EMAIL --password-file password.txt --storage file",
    "auth status": "",
    "auth logout": "--storage file",
    "auth doctor": "",
    "auth ping": "",
    "auth setup": "",
    "accounts list": "",
    "accounts show": "ACCOUNT_ID",
    "accounts refresh": "--active-linked --wait",
    "accounts refresh-status": "--active-linked",
    "accounts history": "ACCOUNT_ID",
    "accounts holdings": "ACCOUNT_ID",
    "accounts recent-balances": "--start 2026-01-01",
    "accounts snapshots": "--start 2026-01-01",
    "accounts aggregate-snapshots": "--start 2026-01-01 --end 2026-01-31",
    "accounts create": '--name "Cash" --type depository --subtype cash --balance 0',
    "accounts create-investments": '--name "Brokerage" --subtype brokerage',
    "accounts clone-filtered": 'ACCOUNT_ID --name "Filtered account" --dry-run',
    "accounts update": 'ACCOUNT_ID --name "New name"',
    "accounts delete": "ACCOUNT_ID --yes",
    "accounts upload-history": "ACCOUNT_ID history.csv",
    "transactions list": "--limit 100",
    "transactions update": 'TXN_ID --notes "Receipt checked" --dry-run',
    "transactions create": (
        '--date 2026-01-01 --account ACCOUNT_ID --amount -25 --merchant "Cash" '
        "--category CATEGORY_ID"
    ),
    "transactions upsert": (
        '--date 2026-01-01 --account ACCOUNT_ID --amount -25 --merchant "Cash" '
        "--category CATEGORY_ID"
    ),
    "transactions show": "TXN_ID",
    "transactions delete": "TXN_ID --yes",
    "transactions duplicates": "--start 2026-01-01 --end 2026-01-31",
    "transactions attach": "TXN_ID receipt.pdf --dry-run",
    "transactions batch-update": 'TXN_ID --notes "Receipt checked" --dry-run',
    "transactions tags list": "",
    "transactions tags create": '--name Tax --color "#2f855a"',
    "transactions tags set": "TXN_ID --tag TAG_ID",
    "transactions tags remove": "TXN_ID --tag TAG_ID",
    "transactions tags clear": "TXN_ID",
    "transactions splits show": "TXN_ID",
    "transactions splits update": "TXN_ID --splits-file splits.json",
    "budgets list": "",
    "budgets reset": "--start 2026-01-01",
    "budgets set": "--category CATEGORY_ID --amount 800 --start 2026-01-01",
    "budgets flexible": "--amount 1000 --start 2026-01-01",
    "budgets flex-rollover": "--start-month 2026-01-01 --starting-balance 0 --enabled",
    "budgets settings": "",
    "cashflow summary": "--preset this-month",
    "cashflow detail": "--preset this-month",
    "cashflow transaction-summary": "",
    "cashflow recurring": "--preset this-month",
    "cashflow credit-history": "",
    "cashflow subscription": "",
    "cashflow institutions": "",
    "categories list": "",
    "categories groups": "",
    "categories create": '--group GROUP_ID --name "New category"',
    "categories delete": "CATEGORY_ID --yes",
    "investments holdings": "",
    "investments securities": "VTI --limit 100",
    "investments holding create": "--account ACCOUNT_ID --security SECURITY_ID --quantity 10",
    "investments holding update": "HOLDING_ID --account ACCOUNT_ID --quantity 10",
    "investments holding delete": "HOLDING_ID --account ACCOUNT_ID --yes",
    "mcp status": "",
    "mcp start": "--transport stdio",
    "receipts upload": "TXN_ID receipt.pdf --dry-run",
    "receipts list": "TXN_ID",
    "receipts missing": "--limit 100",
    "receipts inbox": "--status pending_matches",
    "receipts show": "RECEIPT_ID",
    "receipts match": "RECEIPT_ID TXN_ID --dry-run",
    "report list": "",
    "report show": "REPORT_ID",
    "report create": (
        '--name "Tagged cash flow" '
        '--url "https://app.monarch.com/reports/cash-flow?tags=TAG_ID" --dry-run'
    ),
    "report rename": 'REPORT_ID --name "New name" --dry-run',
    "report delete": "REPORT_ID --dry-run",
}

VARIANTS = {
    "api": "GetAccounts --query 'query GetAccounts { accounts { id displayName } }'",
    "auth login": "--email EMAIL --password-file password.txt --storage file --mfa-code CODE",
    "accounts list": "--fields id,name,balance",
    "accounts show": "ACCOUNT_ID --fields id,displayName,includeInNetWorth",
    "accounts refresh": "--account ACCOUNT_ID --wait --timeout 300 --delay 10",
    "accounts refresh-status": "--account ACCOUNT_ID",
    "transactions list": "--account ACCOUNT_ID --needs-review --limit 100",
    "transactions show": "TXN_ID --full",
    "transactions update": "TXN_ID --amount -25 --dry-run",
    "transactions batch-update": 'TXN_ID OTHER_TXN_ID --notes "Receipt checked" --dry-run',
    "budgets set": "--group GROUP_ID --amount 1500 --start 2026-01-01",
    "budgets flex-rollover": "--disabled",
    "budgets settings": "--fields budgetSystem,flexExpenseRolloverPeriod",
    "investments holdings": "--account ACCOUNT_ID --detailed",
    "mcp start": "--transport streamable-http",
    "receipts inbox": "--status completed --limit 100 --offset 100",
    "receipts match": "RECEIPT_ID TXN_ID --retail-transaction RETAIL_TXN_ID --dry-run",
    "report create": (
        '--name "New report" --filters-file filters.json --view-file view.json --dry-run'
    ),
    "report delete": "REPORT_ID --yes",
}


def examples_for(command: click.Command, path: str) -> list[str]:
    key = path.removeprefix("monarch").strip()
    if not key:
        return ["monarch", "monarch accounts list", "monarch transactions list --needs-review"]
    if isinstance(command, click.Group):
        preferred = sorted(
            command.commands,
            key=lambda name: (
                0
                if name in {"list", "status", "summary"}
                else 1
                if name in {"show", "history", "holdings"}
                else 2,
                name,
            ),
        )
        examples = []
        for name in preferred:
            child = command.commands[name]
            if not child.hidden:
                examples.append(examples_for(child, f"{path} {name}")[0])
            if len(examples) == 2:
                break
        return examples
    if key not in BASES:
        raise ValueError(f"Add reviewed AXI help examples for {path}")
    base = f"{path} {BASES[key]}".strip()
    second = f"{path} {VARIANTS[key]}" if key in VARIANTS else f"{base} --json"
    return [base, second]


def _default(value: Any) -> str:
    if value is getattr(click.core, "UNSET", None):
        return "none"
    if isinstance(value, Enum):
        return str(value.value)
    if value is None:
        return "none"
    if isinstance(value, bool):
        return str(value).lower()
    if value == "":
        return '""'
    if isinstance(value, (list, tuple)) and not value:
        return "none"
    return str(value)


def configure_help(command: click.Command, path: str) -> None:
    if command.hidden:
        return
    # Replace outdated default-format examples, retaining the command explanation.
    command.help = re.split(r"\n\s*Examples:", command.help or "", maxsplit=1)[0].rstrip()
    existing = (command.epilog or "").split("Examples:")[0].strip()
    command.epilog = (
        (existing + "\n\n" if existing else "")
        + "Examples:\n\n"
        + "\n\n".join(f"  {example}" for example in examples_for(command, path))
    )
    for parameter in command.params:
        if not isinstance(parameter, click.Option) or parameter.hidden:
            continue
        if "--format" in parameter.opts:
            parameter.help = (
                "Output format (toon, json, plain, table, csv, compact). Default: toon."
            )
        elif not parameter.required and "Default:" not in (parameter.help or ""):
            parameter.help = (
                f"{(parameter.help or '').rstrip('.')}\nDefault: {_default(parameter.default)}."
            )
        parameter.show_default = False  # Defaults are explicit even for false/none flags.


def _positionals(context: click.Context, argv: list[str]) -> list[str]:
    """Recover only unambiguous positional input; never run parser callbacks."""
    chain = []
    node = context
    while node.parent:
        chain.append(node)
        node = node.parent
    cursor = 0
    for child in reversed(chain):
        flags = {
            flag: p
            for p in node.command.params
            if isinstance(p, click.Option)
            for flag in [*p.opts, *p.secondary_opts]
        }
        while cursor < len(argv):
            token = argv[cursor]
            if token == child.info_name:
                cursor += 1
                break
            option = flags.get(token.partition("=")[0])
            cursor += 1 + (
                option.nargs if option and not option.is_flag and "=" not in token else 0
            )
        node = child
    flags = {
        flag: p
        for p in context.command.params
        if isinstance(p, click.Option)
        for flag in [*p.opts, *p.secondary_opts]
    }
    found: list[str] = []
    while cursor < len(argv):
        token = argv[cursor]
        if token == "--":
            return [*found, *argv[cursor + 1 :]]
        option = flags.get(token.partition("=")[0])
        if option:
            cursor += 1 + (option.nargs if not option.is_flag and "=" not in token else 0)
            continue
        if token.startswith("-"):
            break  # Unknown options have unknown arity; later values are ambiguous.
        found.append(token)
        cursor += 1
    return found


def repair_example(context: click.Context, invalid: click.Parameter | None = None) -> str:
    """Repair missing/invalid input with a complete example and known target IDs."""
    import shlex

    from .agent_context import options

    path = context.command_path
    # Click runners and alternate console-script names can change the root label.
    path = "monarch" + (" " + " ".join(path.split()[1:]) if " " in path else "")
    read_example = (
        path == "monarch api"
        and invalid is not None
        and invalid.name in {"operation", "query", "query_file"}
    )
    sample = shlex.split(examples_for(context.command, path)[1 if read_example else 0])
    provided = options().get("argv", [])
    position = len(path.split())
    positional = _positionals(context, provided)
    argument_index = 0
    for parameter in context.command.params:
        if read_example and parameter.name in {"operation", "query", "query_file"}:
            continue
        if parameter is invalid or not parameter.expose_value:
            continue
        value = context.params.get(parameter.name or "")
        if isinstance(parameter, click.Argument):
            if (value is None or value == () or value == []) and argument_index < len(positional):
                value = (
                    tuple(positional[argument_index:])
                    if parameter.nargs == -1
                    else positional[argument_index]
                )
            argument_index += (
                len(value) if parameter.nargs == -1 and isinstance(value, tuple) else 1
            )
            if value is not None and value != () and value != []:
                replacement = [str(v) for v in value] if parameter.nargs == -1 else [str(value)]
                sample[position : position + 1] = replacement
                position += len(replacement)
            else:
                position += 1
        elif isinstance(parameter, click.Option) and not parameter.is_flag:
            if parameter.name in {"format", "json_output", "password", "mfa_code"}:
                continue
            values = []
            for index, token in enumerate(provided):
                if token in parameter.opts and index + 1 < len(provided):
                    values.append(provided[index + 1])
                elif token.partition("=")[0] in parameter.opts and "=" in token:
                    values.append(token.partition("=")[2])
            if not values:
                continue
            if not parameter.multiple:
                values = values[-1:]
            replacement = [part for item in values for part in (parameter.opts[-1], str(item))]
            existing = next((sample.index(flag) for flag in parameter.opts if flag in sample), None)
            if existing is not None:
                sample[existing : existing + 2] = replacement
            else:
                sample.extend(replacement)
    return shlex.join(sample)
