"""Black-box AXI contracts through the public command tree."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.core.exceptions import APIError
from monarch_cli.main import app

runner = CliRunner()


def reports():
    return [
        {
            "id": "r1",
            "displayName": "Trip",
            "transactionFilterSet": {"tags": [{"id": "1"}]},
            "reportView": {"analysisScope": "cash_flow", "chartType": "sankey"},
            "notes": "large detail",
        }
    ]


def invoke_reports(args, rows=None):
    with (
        patch("monarch_cli.commands.report.get_authenticated_client"),
        patch(
            "monarch_cli.commands.report.list_reports",
            new_callable=AsyncMock,
            return_value=reports() if rows is None else rows,
        ),
    ):
        return runner.invoke(app, ["report", "list", *args])


def test_default_toon_has_small_schema_and_count():
    result = invoke_reports([])
    assert result.exit_code == 0, result.output
    assert "count: 1" in result.stdout
    assert "total_count: 1" in result.stdout
    assert "{id,displayName,type}" in result.stdout
    assert "r1,Trip,cash_flow" in result.stdout
    assert "transactionFilterSet" not in result.stdout
    assert "large detail" not in result.stdout
    assert "monarch report show r1" in result.stdout
    assert result.stderr == ""


def test_explicit_json_keeps_full_original_schema():
    result = invoke_reports(["--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == reports()


def test_common_fields_after_command():
    result = invoke_reports(["--fields", "id,reportView.chartType"])
    assert result.exit_code == 0, result.output
    assert "{id,reportView.chartType}" in result.stdout
    assert "r1,sankey" in result.stdout
    assert "displayName" not in result.stdout


def test_global_fields_and_explicit_json_projection():
    with (
        patch("monarch_cli.commands.report.get_authenticated_client"),
        patch(
            "monarch_cli.commands.report.list_reports",
            new_callable=AsyncMock,
            return_value=reports(),
        ),
    ):
        result = runner.invoke(app, ["--fields", "id", "report", "list", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"id": "r1"}]


def test_unknown_fields_are_usage_errors():
    result = invoke_reports(["--fields", "misspelled"])
    assert result.exit_code == 2
    assert "Unknown field" in result.stdout
    assert result.stderr == ""


def test_empty_list_is_definitive():
    result = invoke_reports([], rows=[])
    assert result.exit_code == 0, result.output
    assert "count: 0" in result.stdout
    assert "total_count: 0" in result.stdout
    assert "No report list results" in result.stdout
    assert "items: []" in result.stdout


def test_detail_truncation_and_full_escape_hatch():
    data = {"id": "r1", "notes": "x" * 1800}
    with (
        patch("monarch_cli.commands.report.get_authenticated_client"),
        patch(
            "monarch_cli.commands.report.show_report",
            new_callable=AsyncMock,
            return_value=data,
        ),
    ):
        compact = runner.invoke(app, ["report", "show", "r1"])
        full = runner.invoke(app, ["report", "show", "r1", "--full"])
        json_result = runner.invoke(app, ["report", "show", "r1", "--json"])
    assert compact.exit_code == full.exit_code == json_result.exit_code == 0
    assert "1800 chars total" in compact.stdout
    assert "monarch report show r1 --full" in compact.stdout
    assert "x" * 1800 not in compact.stdout
    assert "x" * 1800 in full.stdout
    assert "--full" not in full.stdout
    assert json.loads(json_result.stdout) == data


@pytest.mark.parametrize("args", [["report", "create"], ["accunts"], ["report", "list", "--wrong"]])
def test_parser_errors_are_structured_stdout(args):
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert "error:" in result.stdout
    assert "help" in result.stdout
    assert result.stderr == ""


def test_json_parser_error_before_root_callback():
    result = runner.invoke(app, ["report", "create", "--json"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["code"] == "INVALID_INPUT"
    assert "--name" in result.stdout
    assert result.stderr == ""


def test_runtime_error_uses_stdout_and_actionable_help():
    with patch(
        "monarch_cli.commands.report.get_authenticated_client", side_effect=APIError("denied")
    ):
        result = runner.invoke(app, ["report", "list"])
    assert result.exit_code == 1
    assert "error: true" in result.stdout
    assert "denied" in result.stdout
    assert "monarch auth ping --json" in result.stdout
    assert result.stderr == ""


def test_common_format_flag_for_command_without_local_format():
    with patch("monarch_cli.commands.auth.get_storage_info", return_value={"active_backend": None}):
        result = runner.invoke(app, ["auth", "status", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["authenticated"] is False


def test_transaction_total_and_pagination_hint_preserve_filters():
    rows = [{"id": "t1", "date": "2026-11-19", "amount": -5, "merchant": {"name": "Shop"}}]
    with patch("monarch_cli.commands.transactions.get_authenticated_client") as client:
        client.return_value.get_transactions = AsyncMock(
            return_value={"allTransactions": {"totalCount": 42, "results": rows}}
        )
        result = runner.invoke(
            app,
            [
                "transactions",
                "list",
                "--account",
                "a1",
                "--tag",
                "tag1",
                "--limit",
                "1",
                "--offset",
                "2",
            ],
        )
    assert result.exit_code == 0, result.output
    assert "total_count: 42" in result.stdout
    assert "--offset 3" in result.stdout
    assert "--account a1" in result.stdout and "--tag tag1" in result.stdout


def test_receipt_page_is_compact_and_selectable():
    page = {
        "total_count": 3,
        "offset": 0,
        "limit": 1,
        "next_offset": 1,
        "results": [
            {
                "id": "r1",
                "status": "pending_matches",
                "vendor": "user_import",
                "orders": [{"merchantName": "Shop", "grandTotal": 12}],
                "attachments": [],
            }
        ],
    }
    with (
        patch("monarch_cli.commands.receipts.get_authenticated_client"),
        patch(
            "monarch_cli.commands.receipts.fetch_inbox",
            new_callable=AsyncMock,
            return_value=page,
        ),
    ):
        result = runner.invoke(app, ["receipts", "inbox", "--fields", "id,status"])
    assert result.exit_code == 0, result.output
    assert "{id,status}" in result.stdout
    assert "total_count: 3" in result.stdout
    assert "orders" not in result.stdout


def test_full_hint_preserves_detail_filters():
    with patch("monarch_cli.commands.transactions.get_authenticated_client") as client:
        client.return_value.get_transaction_details = AsyncMock(return_value={"notes": "x" * 1800})
        result = runner.invoke(app, ["transactions", "show", "t1", "--no-redirect-posted"])
    assert result.exit_code == 0, result.output
    assert "monarch transactions show t1 --no-redirect-posted --full" in result.stdout


def test_unknown_field_suggests_valid_field_selection():
    result = invoke_reports(["--fields", "misspelled"])
    assert result.exit_code == 2
    assert "monarch report list --fields id" in result.stdout
    assert "auth ping" not in result.stdout


def test_runtime_dependency_details_are_not_leaked():
    secret_error = RuntimeError("monarchmoney dependency traceback: sensitive token")
    with patch("monarch_cli.commands.report.get_authenticated_client", side_effect=secret_error):
        result = runner.invoke(app, ["report", "list"])
    assert result.exit_code == 1
    assert "sensitive token" not in result.stdout
    assert "monarchmoney" not in result.stdout
    assert "--debug" in result.stdout


def test_raw_api_field_flags_do_not_collide_with_projection():
    with patch("monarch_cli.commands.api.get_authenticated_client") as client:
        client.return_value.gql_call = AsyncMock(return_value={"ok": True, "other": 1})
        result = runner.invoke(
            app,
            [
                "api",
                "Example",
                "--query",
                "query Example { accounts { id } }",
                "-F",
                "limit=10",
                "--fields",
                "ok",
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"ok": True}
    assert client.return_value.gql_call.call_args.args[2] == {"limit": 10}


def test_json_equals_format_is_respected_on_parser_error():
    result = runner.invoke(app, ["report", "create", "--format=json"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["code"] == "INVALID_INPUT"
    assert result.stderr == ""


def test_local_json_format_is_respected_on_runtime_error():
    result = invoke_reports(["--format", "json", "--fields", "missing"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"] is True
    assert result.stderr == ""


def test_uncertain_mutation_error_suggests_inspection_not_replay():
    with patch(
        "monarch_cli.commands.report.get_authenticated_client", side_effect=RuntimeError("failed")
    ):
        result = runner.invoke(app, ["report", "create", "--name", "Example"])
    assert result.exit_code == 1
    assert "monarch report list" in result.stdout
    assert "--debug report create" not in result.stdout


def test_capabilities_marks_new_writes_and_hides_native_wire_endpoint():
    import json

    result = runner.invoke(app, ["capabilities", "--json"])
    commands = {item["name"]: item for item in json.loads(result.stdout)["commands"]}
    for command in ["report rename", "receipts match", "transactions batch-update"]:
        assert commands[command]["mutates"] is True
    assert "_session-hook" not in commands
