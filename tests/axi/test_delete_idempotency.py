"""Desired absence is a successful no-op only after a complete validated read."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from monarch_cli.main import app

runner = CliRunner()


@pytest.mark.parametrize("group", ["accounts", "transactions", "categories"])
def test_delete_repeatedly_acknowledges_absence_without_a_write(group):
    client = MagicMock(
        get_accounts=AsyncMock(return_value={"accounts": []}),
        get_transaction_details=AsyncMock(return_value={"getTransaction": None}),
        get_transaction_categories=AsyncMock(return_value={"categories": []}),
        delete_account=AsyncMock(),
        delete_transaction=AsyncMock(),
        delete_transaction_category=AsyncMock(),
        delete_transaction_categories=AsyncMock(),
    )
    with patch(f"monarch_cli.commands.{group}.get_authenticated_client", return_value=client):
        for _ in range(2):
            result = runner.invoke(app, [group, "delete", "123", "--yes", "--json"])
            assert result.exit_code == 0, result.output
            data = json.loads(result.stdout)
            assert data["status"] == "unchanged"
            assert data["id"] == "123"
            assert data["message"] == "Already absent; no write needed."
    for name in [
        "delete_account",
        "delete_transaction",
        "delete_transaction_category",
        "delete_transaction_categories",
    ]:
        getattr(client, name).assert_not_called()


@pytest.mark.parametrize(
    "group,method",
    [
        ("accounts", "get_accounts"),
        ("transactions", "get_transaction_details"),
        ("categories", "get_transaction_categories"),
    ],
)
@pytest.mark.parametrize("response", [{}, None, {"errors": ["permission denied"]}])
def test_bad_or_incomplete_read_is_never_treated_as_absence(group, method, response):
    client = MagicMock()
    setattr(client, method, AsyncMock(return_value=response))
    with patch(f"monarch_cli.commands.{group}.get_authenticated_client", return_value=client):
        result = runner.invoke(app, [group, "delete", "123", "--yes", "--json"])
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"] is True
    for name in [
        "delete_account",
        "delete_transaction",
        "delete_transaction_category",
        "delete_transaction_categories",
    ]:
        getattr(client, name).assert_not_called()


@pytest.mark.parametrize("group", ["accounts", "transactions", "categories"])
def test_present_delete_is_not_retried_or_reported_success_when_unconfirmed(group):
    client = MagicMock(
        get_accounts=AsyncMock(return_value={"accounts": [{"id": "123"}]}),
        get_transaction_details=AsyncMock(return_value={"getTransaction": {"id": "123"}}),
        get_transaction_categories=AsyncMock(return_value={"categories": [{"id": "123"}]}),
        delete_account=AsyncMock(
            return_value={"deleteAccount": {"deleted": False, "errors": None}}
        ),
        delete_transaction=AsyncMock(return_value=False),
        delete_transaction_category=AsyncMock(return_value=False),
    )
    with patch(f"monarch_cli.commands.{group}.get_authenticated_client", return_value=client):
        result = runner.invoke(app, [group, "delete", "123", "--yes", "--json"])
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"] is True
    method = {
        "accounts": "delete_account",
        "transactions": "delete_transaction",
        "categories": "delete_transaction_category",
    }[group]
    getattr(client, method).assert_awaited_once()


def test_partial_category_absence_deletes_only_existing_unique_ids():
    client = MagicMock(
        get_transaction_categories=AsyncMock(return_value={"categories": [{"id": "present"}]}),
        delete_transaction_category=AsyncMock(return_value=True),
    )
    with patch("monarch_cli.commands.categories.get_authenticated_client", return_value=client):
        result = runner.invoke(
            app, ["categories", "delete", "gone", "present", "present", "--yes", "--json"]
        )
    assert result.exit_code == 0, result.output
    client.delete_transaction_category.assert_awaited_once_with("present")
    client.delete_transaction_categories.assert_not_called()
    assert json.loads(result.stdout)["status"] == "deleted"


@pytest.mark.parametrize(
    "payload", [{"portfolio": {}}, {}, {"portfolio": {"aggregateHoldings": {"edges": None}}}]
)
def test_malformed_holdings_never_prove_absence(payload):
    client = MagicMock(get_account_holdings=AsyncMock(return_value=payload), gql_call=AsyncMock())
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        result = runner.invoke(
            app, ["investments", "holding", "delete", "h1", "--account", "101", "--yes", "--json"]
        )
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"] is True
    client.gql_call.assert_not_called()


def test_holding_already_absent_is_success_without_a_write():
    client = MagicMock(
        get_account_holdings=AsyncMock(
            return_value={"portfolio": {"aggregateHoldings": {"edges": []}}}
        ),
        gql_call=AsyncMock(),
    )
    with patch("monarch_cli.commands.investments.get_authenticated_client", return_value=client):
        result = runner.invoke(
            app, ["investments", "holding", "delete", "h1", "--account", "101", "--yes", "--json"]
        )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "unchanged"
    client.gql_call.assert_not_called()


def test_report_already_absent_is_success_and_preview_does_not_write():
    client = MagicMock(gql_call=AsyncMock(return_value={"reportConfigurations": []}))
    with patch("monarch_cli.commands.report.get_authenticated_client", return_value=client):
        for flags in [["--yes"], ["--dry-run"]]:
            result = runner.invoke(app, ["report", "delete", "r1", *flags, "--json"])
            assert result.exit_code == 0, result.output
            data = json.loads(result.stdout)
            assert data["status"] == "unchanged"
            assert data["verified"] is True
    assert client.gql_call.await_count == 2
    assert all(
        call.kwargs["operation"] == "Common_GetReportConfigurations"
        for call in client.gql_call.await_args_list
    )


@pytest.mark.parametrize(
    "group,method",
    [
        ("accounts", "delete_account"),
        ("transactions", "delete_transaction"),
        ("categories", "delete_transaction_category"),
    ],
)
def test_uncertain_delete_is_not_retried_and_does_not_leak_dependency_text(group, method):
    client = MagicMock(
        get_accounts=AsyncMock(return_value={"accounts": [{"id": "123"}]}),
        get_transaction_details=AsyncMock(return_value={"getTransaction": {"id": "123"}}),
        get_transaction_categories=AsyncMock(return_value={"categories": [{"id": "123"}]}),
    )
    write = AsyncMock(side_effect=ConnectionError("SDK PRIVATE TOKEN secret-value"))
    setattr(client, method, write)
    with patch(f"monarch_cli.commands.{group}.get_authenticated_client", return_value=client):
        result = runner.invoke(app, [group, "delete", "123", "--yes", "--json"])
    assert result.exit_code == 1
    assert "secret-value" not in result.stdout
    assert "SDK" not in result.stdout
    write.assert_awaited_once()


@pytest.mark.parametrize("group", ["accounts", "transactions", "categories"])
def test_first_delete_changes_state_and_repetition_does_not_write_again(group):
    present = True

    async def read_accounts():
        return {"accounts": [{"id": "123"}] if present else []}

    async def read_transaction(**kwargs):
        assert kwargs == {"transaction_id": "123", "redirect_posted": False}
        return {"getTransaction": {"id": "123"} if present else None}

    async def read_categories():
        return {"categories": [{"id": "123"}] if present else []}

    async def delete(*_args, **_kwargs):
        nonlocal present
        assert present
        present = False
        return {"deleteAccount": {"deleted": True, "errors": None}} if group == "accounts" else True

    write = AsyncMock(side_effect=delete)
    client = MagicMock(
        get_accounts=AsyncMock(side_effect=read_accounts),
        get_transaction_details=AsyncMock(side_effect=read_transaction),
        get_transaction_categories=AsyncMock(side_effect=read_categories),
    )
    setattr(
        client,
        {
            "accounts": "delete_account",
            "transactions": "delete_transaction",
            "categories": "delete_transaction_category",
        }[group],
        write,
    )
    with patch(f"monarch_cli.commands.{group}.get_authenticated_client", return_value=client):
        first = runner.invoke(app, [group, "delete", "123", "--yes", "--json"])
        second = runner.invoke(app, [group, "delete", "123", "--yes", "--json"])
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert json.loads(first.stdout)["status"] == "deleted"
    assert json.loads(second.stdout)["status"] == "unchanged"
    write.assert_awaited_once()


def test_projection_error_after_delete_never_suggests_replaying_the_write():
    import shlex

    client = MagicMock(
        get_transaction_details=AsyncMock(return_value={"getTransaction": {"id": "123"}}),
        delete_transaction=AsyncMock(return_value=True),
    )
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = runner.invoke(
            app, ["transactions", "delete", "123", "--yes", "--fields", "missing", "--json"]
        )
    assert result.exit_code == 2
    hint = json.loads(result.stdout)["help"][0]
    assert shlex.split(hint) == ["monarch", "transactions", "show", "123"]
    client.delete_transaction.assert_awaited_once()


def test_malformed_field_selection_is_rejected_before_deleting():
    with patch("monarch_cli.commands.transactions.get_authenticated_client") as client:
        result = runner.invoke(app, ["transactions", "delete", "123", "--yes", "--fields", ","])
    assert result.exit_code == 2, result.output
    client.assert_not_called()


def test_primitive_output_selection_after_write_never_offers_a_replay():
    client = MagicMock(gql_call=AsyncMock(return_value=True))
    with patch("monarch_cli.commands.api.get_authenticated_client", return_value=client):
        result = runner.invoke(
            app,
            [
                "api",
                "Example",
                "--query",
                "mutation Example { unused }",
                "--fields",
                "id",
                "--json",
            ],
        )
    assert result.exit_code == 2, result.output
    assert "mutation" not in str(json.loads(result.stdout)["help"])
    client.gql_call.assert_awaited_once()


@pytest.mark.parametrize(
    "group,key,method",
    [
        ("accounts", "accounts", "get_accounts"),
        ("categories", "categories", "get_transaction_categories"),
    ],
)
@pytest.mark.parametrize(
    "rows", [[{}], [{"id": "other"}, {"id": None}], [{"id": "other"}, {"id": "other"}]]
)
def test_invalid_ids_cannot_establish_absence(group, key, method, rows):
    client = MagicMock()
    setattr(client, method, AsyncMock(return_value={key: rows}))
    with patch(f"monarch_cli.commands.{group}.get_authenticated_client", return_value=client):
        result = runner.invoke(app, [group, "delete", "123", "--yes", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"] is True
    client.delete_account.assert_not_called()
    client.delete_transaction_category.assert_not_called()


def test_bulk_category_partial_failure_is_not_success_or_a_retry():
    client = MagicMock(
        get_transaction_categories=AsyncMock(
            return_value={"categories": [{"id": "a"}, {"id": "b"}]}
        ),
        delete_transaction_categories=AsyncMock(
            return_value=[True, RuntimeError("PRIVATE SDK secret")]
        ),
    )
    with patch("monarch_cli.commands.categories.get_authenticated_client", return_value=client):
        result = runner.invoke(app, ["categories", "delete", "a", "b", "--yes", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"] is True
    assert "PRIVATE SDK" not in result.stdout
    client.delete_transaction_categories.assert_awaited_once_with(["a", "b"])


def test_transaction_delete_uses_the_installed_sdk_get_transaction_field():
    client = MagicMock(
        get_transaction_details=AsyncMock(return_value={"getTransaction": None}),
        delete_transaction=AsyncMock(),
    )
    with patch("monarch_cli.commands.transactions.get_authenticated_client", return_value=client):
        result = runner.invoke(app, ["transactions", "delete", "123", "--yes", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "unchanged"
    client.delete_transaction.assert_not_called()


async def test_preflight_contract_matches_real_sdk_query_without_network():
    from graphql.language import FieldNode, OperationDefinitionNode
    from monarchmoney import MonarchMoney

    from monarch_cli.commands._mutation import transaction_exists

    client = MonarchMoney()

    async def response_for_query(*, operation, graphql_query, variables):
        assert operation == "GetTransactionDrawer"
        document = getattr(graphql_query, "document", graphql_query)
        root = next(
            node for node in document.definitions if isinstance(node, OperationDefinitionNode)
        )
        field = next(
            node
            for node in root.selection_set.selections
            if isinstance(node, FieldNode)
            and any(argument.name.value == "id" for argument in node.arguments)
        )
        name = field.alias.value if field.alias else field.name.value
        return {name: {"id": variables["id"]}}

    client.gql_call = AsyncMock(side_effect=response_for_query)
    raw = await client.get_transaction_details("123", redirect_posted=False)
    assert transaction_exists(raw, "123") is True
    client.gql_call.assert_awaited_once()
