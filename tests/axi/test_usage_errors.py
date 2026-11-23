"""Locally invalid operations fail with useful repair commands before dependencies."""

import json
from unittest.mock import patch

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from monarch_cli.main import app


@pytest.mark.parametrize(
    "words",
    [
        ["accounts", "update", "ACCOUNT_ID"],
        ["accounts", "delete", "ACCOUNT_ID"],
        ["transactions", "update", "TXN_ID"],
        ["transactions", "delete", "TXN_ID"],
        ["transactions", "batch-update"],
        ["transactions", "batch-update", "TXN_ID"],
        ["categories", "delete", "CATEGORY_ID"],
        ["budgets", "set", "--amount", "100"],
        ["transactions", "splits", "update", "TXN_ID"],
        ["transactions", "splits", "update", "TXN_ID", "--splits-json", "{}"],
        ["transactions", "splits", "update", "TXN_ID", "--splits-json", "{bad"],
    ],
)
def test_invalid_operation_has_usage_code_and_copyable_safe_hint(words):
    with patch(
        f"monarch_cli.commands.{words[0]}.get_authenticated_client",
        side_effect=AssertionError("no dependency"),
    ) as dependency:
        result = CliRunner().invoke(app, [*words, "--json"])
    dependency.assert_not_called()
    assert result.exit_code == 2, result.output
    data = json.loads(result.stdout)
    assert data["error"] is True and data["code"] == "INVALID_INPUT"
    assert data["help"] and data["help"] != ["monarch auth ping --json"]
    assert result.stderr == ""


def test_parser_fix_supplies_all_required_flags_and_keeps_account_id():
    import shlex

    result = CliRunner().invoke(app, ["transactions", "create", "--account", "123", "--json"])
    assert result.exit_code == 2
    hint = json.loads(result.stdout)["help"][0]
    assert "--account 123" in hint
    command = get_command(app).commands["transactions"].commands["create"]
    args = shlex.split(hint)[3:]
    ctx = command.make_context("create", args)
    assert ctx.params["account"] == "123"
    assert all(ctx.params.get(p.name) is not None for p in command.params if p.required)
    assert "--dry-run" not in hint  # This operation has no preview flag.


@pytest.mark.parametrize(
    "words,required",
    [
        (["transactions", "show", "123", "--jso"], ["show", "123"]),
        (
            ["report", "rename", "r1", "--name", "Updated", "--unknown"],
            ["rename", "r1", "--name", "Updated", "--dry-run"],
        ),
        (["receipts", "match", "r1", "t1", "--unknown"], ["match", "r1", "t1", "--dry-run"]),
        (
            [
                "transactions",
                "list",
                "--account",
                "a1",
                "--account",
                "a2",
                "--limit",
                "50",
                "--unknown",
            ],
            ["--account", "a1", "--account", "a2", "--limit", "50"],
        ),
    ],
)
def test_unknown_option_repair_retains_targets_and_filters(words, required):
    import shlex

    result = CliRunner().invoke(app, ["--json", *words])
    assert result.exit_code == 2
    command = shlex.split(json.loads(result.stdout)["help"][0])
    for token in required:
        assert token in command, command
    assert "--unknown" not in command
    root = get_command(app)
    ctx = root.make_context("monarch", command[1:])
    current = root
    with ctx:
        while isinstance(current, click.Group):
            _, child, rest = current.resolve_command(ctx, ctx._protected_args + ctx.args)
            assert child is not None
            ctx = child.make_context(child.name, rest, parent=ctx)
            current = child


def test_validation_repair_does_not_copy_the_invalid_tag_value():
    import shlex

    result = CliRunner().invoke(app, ["transactions", "tags", "set", "123", "--tag", "", "--json"])
    assert result.exit_code == 2
    hint = shlex.split(json.loads(result.stdout)["help"][0])
    assert hint[1:5] == ["transactions", "tags", "set", "123"]
    assert hint[hint.index("--tag") + 1]


def test_missing_api_query_repair_is_a_complete_safe_read_example():
    import shlex

    from graphql import get_operation_ast, parse

    result = CliRunner().invoke(app, ["api", "Example", "--json"])
    assert result.exit_code == 2
    hint = shlex.split(json.loads(result.stdout)["help"][0])
    assert "--query" in hint
    query = hint[hint.index("--query") + 1]
    operation = get_operation_ast(parse(query), hint[2])
    assert operation is not None and operation.operation.value == "query"


@pytest.mark.parametrize(
    "words",
    [
        ["api", "Example", "--query-file"],
        ["api", "--query", "query X { accounts { id } }"],
    ],
)
def test_incomplete_api_parser_input_has_a_valid_read_repair(words):
    import shlex

    from graphql import get_operation_ast, parse

    response = CliRunner().invoke(app, ["--json", *words])
    assert response.exit_code == 2
    hint = shlex.split(json.loads(response.stdout)["help"][0])
    assert "--query" in hint
    op = get_operation_ast(parse(hint[hint.index("--query") + 1]), hint[2])
    assert op is not None and op.operation.value == "query"
