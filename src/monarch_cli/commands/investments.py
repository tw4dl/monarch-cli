"""Investment commands for Monarch CLI."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, cast

import typer
from graphql import DocumentNode, parse

from ..core.adapter import get_authenticated_client
from ..core.async_utils import run_api_call
from ..core.error_handler import handle_errors
from ..core.exceptions import APIError, ValidationError
from ..output import OutputFormat, output
from ..output.progress import spinner

app = typer.Typer(
    help="Investment holdings",
    no_args_is_help=True,
)
holding_app = typer.Typer(
    help="Create, update, and delete manual investment holdings",
    no_args_is_help=True,
)
app.add_typer(holding_app, name="holding")

_SECURITY_SEARCH_QUERY = parse(
    """
    query SecuritySearch($search: String!, $limit: Int, $orderByPopularity: Boolean) {
      securities(search: $search, limit: $limit, orderByPopularity: $orderByPopularity) {
        id
        name
        ticker
        type
        typeDisplay
        currentPrice
        currentPriceUpdatedAt
        closingPrice
        closingPriceUpdatedAt
      }
    }
    """
)
_CREATE_HOLDING_MUTATION = parse(
    """
    mutation Common_CreateManualHolding($input: CreateManualHoldingInput!) {
      createManualHolding(input: $input) {
        holding { id ticker }
        errors { message code }
      }
    }
    """
)
_UPDATE_HOLDING_MUTATION = parse(
    """
    mutation Common_UpdateHolding($input: UpdateHoldingInput!) {
      updateHolding(input: $input) {
        holding { id quantity }
        errors { message code }
      }
    }
    """
)
_DELETE_HOLDING_MUTATION = parse(
    """
    mutation Common_DeleteHolding($id: ID!) {
      deleteHolding(id: $id) {
        deleted
        errors { message code }
      }
    }
    """
)
_DETAILED_HOLDINGS_QUERY = parse(
    """
    query Web_GetHoldingsDetailed($input: PortfolioInput) {
      portfolio(input: $input) {
        aggregateHoldings {
          edges {
            node {
              id
              quantity
              basis
              totalValue
              lastSyncedAt
              holdings {
                id
                type
                typeDisplay
                name
                ticker
                quantity
                value
                closingPrice
                closingPriceUpdatedAt
                costBasis
                isManual
              }
              security {
                id
                name
                type
                typeDisplay
                ticker
                currentPrice
                currentPriceUpdatedAt
                closingPrice
                closingPriceUpdatedAt
              }
            }
          }
        }
      }
    }
    """
)


def _nested_value(data: dict[str, Any], key: str, nested_key: str) -> Any:
    """Read a nested value from an optional dictionary."""
    value = data.get(key)
    if isinstance(value, dict):
        return value.get(nested_key)
    return None


def _is_investment_account(account: dict[str, Any]) -> bool:
    """Check whether account metadata represents an investment account."""
    return bool(_nested_value(account, "type", "name") == "brokerage")


def _get_accounts_call(client: Any) -> Awaitable[dict[str, Any]]:
    """Call upstream get_accounts with an explicit type for mypy."""
    return cast(Awaitable[dict[str, Any]], client.get_accounts())


def _get_account_holdings_call(client: Any, account_id: int) -> Awaitable[dict[str, Any]]:
    """Call upstream get_account_holdings with an explicit type for mypy."""
    return cast(Awaitable[dict[str, Any]], client.get_account_holdings(account_id))


def _get_account_holdings_factory(
    client: Any,
    account_id: int,
) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Create a holdings call factory with account_id bound for retries."""

    def call() -> Awaitable[dict[str, Any]]:
        return _get_account_holdings_call(client, account_id)

    return call


def _gql_call(
    client: Any,
    operation: str,
    query: DocumentNode,
    variables: dict[str, Any],
) -> Awaitable[dict[str, Any]]:
    """Call the authenticated GraphQL escape hatch with an explicit type."""
    return cast(Awaitable[dict[str, Any]], client.gql_call(operation, query, variables))


def _get_detailed_holdings_call(client: Any, account_id: str) -> Awaitable[dict[str, Any]]:
    """Fetch holdings fields needed to distinguish provider-native values."""
    return _gql_call(
        client,
        "Web_GetHoldingsDetailed",
        _DETAILED_HOLDINGS_QUERY,
        {
            "input": {
                "accountIds": [account_id],
                "includeHiddenHoldings": True,
                "topMoversLimit": 4,
            }
        },
    )


def _get_detailed_holdings_factory(
    client: Any,
    account_id: str,
) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Create a detailed holdings call factory with account_id bound."""

    def call() -> Awaitable[dict[str, Any]]:
        return _get_detailed_holdings_call(client, account_id)

    return call


def _payload_error_message(errors: Any) -> str:
    """Extract a useful message from Monarch mutation payload errors."""
    if isinstance(errors, dict):
        return str(errors.get("message") or errors)
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            return str(first.get("message") or first)
    return str(errors)


def _mutation_payload(data: dict[str, Any], field: str) -> dict[str, Any]:
    """Validate a holding mutation payload and surface Monarch errors."""
    payload = data.get(field)
    if not isinstance(payload, dict):
        raise APIError(
            f"Monarch response did not include {field}.",
            details={"response": data},
        )
    errors = payload.get("errors")
    if errors:
        raise APIError(
            _payload_error_message(errors),
            details={"operation": field, "errors": errors},
        )
    return payload


def _find_holding_by_id(
    holdings_data: dict[str, Any],
    holding_id: str,
) -> dict[str, Any] | None:
    """Find one exact account holding and include its aggregate valuation data."""
    edges = holdings_data.get("portfolio", {}).get("aggregateHoldings", {}).get("edges", [])
    for edge in edges:
        node = edge.get("node") or {}
        security = node.get("security") or {}
        holdings = node.get("holdings") or []
        if isinstance(holdings, dict):
            holdings = [holdings]
        for holding in holdings:
            if not isinstance(holding, dict) or str(holding.get("id")) != holding_id:
                continue
            return {
                "id": holding_id,
                "security_id": str(security.get("id") or node.get("id") or ""),
                "name": holding.get("name") or security.get("name"),
                "ticker": holding.get("ticker") or security.get("ticker"),
                "quantity": holding.get("quantity", node.get("quantity")),
                "costBasis": holding.get("costBasis", node.get("basis")),
                "security_type": holding.get("type") or security.get("type"),
                "is_manual": holding.get("isManual"),
                "current_price": security.get("currentPrice"),
                "total_value": node.get("totalValue"),
            }
    return None


def _read_exact_holding(client: Any, account_id: str, holding_id: str) -> dict[str, Any] | None:
    """Re-query one account and return the requested holding if present."""
    holdings_data = run_api_call(
        _get_account_holdings_factory(client, int(account_id)),
    )
    return _find_holding_by_id(holdings_data, holding_id)


def _assert_holding_changes(
    holding: dict[str, Any],
    *,
    quantity: float | None,
    cost_basis: float | None,
    security_type: str | None,
) -> None:
    """Verify requested holding fields survived the exact account readback."""
    expected = {
        "quantity": quantity,
        "costBasis": cost_basis,
        "security_type": security_type,
    }
    mismatches = {
        key: {"expected": value, "actual": holding.get(key)}
        for key, value in expected.items()
        if value is not None and holding.get(key) != value
    }
    if mismatches:
        raise APIError(
            "Holding mutation did not survive exact readback.",
            details={"holding_id": holding.get("id"), "mismatches": mismatches},
        )


def _select_accounts(
    accounts: list[dict[str, Any]],
    *,
    account_ids: list[str] | None,
    include_hidden: bool,
) -> list[dict[str, Any]]:
    """Select accounts to query for holdings."""
    if account_ids:
        account_by_id = {str(account.get("id")): account for account in accounts}
        return [
            account_by_id.get(
                account_id,
                {
                    "id": account_id,
                    "displayName": account_id,
                    "institution": None,
                    "subtype": None,
                    "isHidden": None,
                },
            )
            for account_id in account_ids
        ]

    return [
        account
        for account in accounts
        if _is_investment_account(account)
        and (account.get("holdingsCount") or 0) > 0
        and (include_hidden or not account.get("isHidden"))
    ]


def _first_holding_info(node: dict[str, Any]) -> dict[str, Any]:
    """Return the first nested holdings object, normalizing API shape variance."""
    holdings = node.get("holdings")
    if isinstance(holdings, list) and holdings:
        first = holdings[0]
        return first if isinstance(first, dict) else {}
    if isinstance(holdings, dict):
        return holdings
    return {}


def _flatten_holdings(
    account: dict[str, Any],
    holdings_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Flatten Monarch holdings API data into tabular rows."""
    edges = holdings_data.get("portfolio", {}).get("aggregateHoldings", {}).get("edges", [])

    rows = []
    for edge in edges:
        node = edge.get("node") or {}
        security = node.get("security") or {}
        holding_info = _first_holding_info(node)
        ticker = security.get("ticker") or holding_info.get("ticker")
        name = security.get("name") or holding_info.get("name")

        rows.append(
            {
                "account_id": str(account.get("id")),
                "account_name": account.get("displayName"),
                "institution": _nested_value(account, "institution", "name"),
                "subtype": _nested_value(account, "subtype", "display"),
                "ticker": ticker,
                "name": name,
                "quantity": node.get("quantity"),
                "basis": node.get("basis"),
                "total_value": node.get("totalValue"),
                "current_price": security.get("currentPrice"),
                "one_day_change_percent": security.get("oneDayChangePercent"),
                "last_synced_at": node.get("lastSyncedAt"),
            }
        )

    return rows


def _aggregate_holdings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate flattened holdings by ticker/name."""
    grouped: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    account_sets: dict[tuple[str | None, str | None], set[str]] = {}

    for row in rows:
        key = (row.get("ticker"), row.get("name"))
        item = grouped.setdefault(
            key,
            {
                "ticker": row.get("ticker"),
                "name": row.get("name"),
                "quantity": 0,
                "basis": 0,
                "total_value": 0,
                "accounts": 0,
            },
        )
        item["quantity"] += row.get("quantity") or 0
        item["basis"] += row.get("basis") or 0
        item["total_value"] += row.get("total_value") or 0
        account_sets.setdefault(key, set()).add(str(row.get("account_id")))

    for key, account_ids in account_sets.items():
        grouped[key]["accounts"] = len(account_ids)

    return sorted(grouped.values(), key=lambda item: item["total_value"], reverse=True)


@app.command("holdings")
@handle_errors
def holdings_cmd(
    account: Annotated[
        list[str] | None,
        typer.Option(
            "-a",
            "--account",
            help="Specific account ID(s) to query. Repeatable.",
        ),
    ] = None,
    include_hidden: Annotated[
        bool,
        typer.Option(
            "--include-hidden",
            help="Include hidden investment accounts when discovering accounts.",
        ),
    ] = False,
    aggregate: Annotated[
        bool,
        typer.Option(
            "--aggregate",
            help="Aggregate holdings across accounts by ticker/name.",
        ),
    ] = False,
    detailed: Annotated[
        bool,
        typer.Option(
            "--detailed",
            help="Include provider-native value, quantity, cost basis, and price metadata.",
        ),
    ] = False,
    raw: Annotated[
        bool,
        typer.Option(
            "--raw",
            help="Output account-wrapped raw API responses.",
        ),
    ] = False,
    format: Annotated[
        OutputFormat | None,
        typer.Option(
            "-f",
            "--format",
            help="Output format (plain, json, table, csv, compact)",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output as JSON (shortcut for --format json)",
        ),
    ] = False,
) -> None:
    """List investment holdings.

    Discovers visible investment accounts with holdings by default. Use
    --account to query specific account IDs, including hidden accounts.

    Examples:
        monarch investments holdings --json
        monarch investments holdings --format table
        monarch investments holdings --aggregate --json
        monarch investments holdings --account ACC123 --json
    """
    output_format = OutputFormat.JSON if json_output else format
    account_ids = list(account) if account else None

    with spinner("Fetching investment holdings..."):
        client = get_authenticated_client()
        accounts_data = run_api_call(lambda: _get_accounts_call(client))
        accounts = accounts_data.get("accounts", [])
        selected_accounts = _select_accounts(
            accounts,
            account_ids=account_ids,
            include_hidden=include_hidden,
        )

        raw_results = []
        rows = []
        for selected_account in selected_accounts:
            account_id_text = str(selected_account.get("id"))
            if detailed:
                holdings_data = run_api_call(
                    _get_detailed_holdings_factory(client, account_id_text)
                )
            else:
                holdings_data = run_api_call(
                    _get_account_holdings_factory(client, int(account_id_text))
                )
            if raw:
                raw_results.append(
                    {
                        "account": selected_account,
                        "holdings": holdings_data,
                    }
                )
            else:
                rows.extend(_flatten_holdings(selected_account, holdings_data))

    if raw:
        output(raw_results, output_format)
        return

    data = _aggregate_holdings(rows) if aggregate else rows
    output(data, output_format)


@app.command("securities")
@handle_errors
def securities_cmd(
    search: Annotated[str, typer.Argument(help="Ticker or security name to search for.")],
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=100, help="Maximum search results."),
    ] = 10,
    format: Annotated[
        OutputFormat | None,
        typer.Option("-f", "--format", help="Output format (plain, json, table, csv, compact)"),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Search Monarch's security catalog by ticker or name."""
    with spinner("Searching securities..."):
        client = get_authenticated_client()
        data = run_api_call(
            lambda: _gql_call(
                client,
                "SecuritySearch",
                _SECURITY_SEARCH_QUERY,
                {"search": search, "limit": limit, "orderByPopularity": True},
            )
        )
    securities = data.get("securities", [])
    output(securities, OutputFormat.JSON if json_output else format)


@holding_app.command("create")
@handle_errors
def holding_create_cmd(
    account: Annotated[str, typer.Option("--account", help="Manual investment account ID.")],
    security: Annotated[str, typer.Option("--security", help="Monarch security ID.")],
    quantity: Annotated[float, typer.Option("--quantity", help="Holding share/unit quantity.")],
    format: Annotated[
        OutputFormat | None,
        typer.Option("-f", "--format", help="Output format (plain, json, table, csv, compact)"),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Create a manual holding and verify it by exact account readback."""
    with spinner("Creating manual holding..."):
        client = get_authenticated_client()
        data = run_api_call(
            lambda: _gql_call(
                client,
                "Common_CreateManualHolding",
                _CREATE_HOLDING_MUTATION,
                {
                    "input": {
                        "accountId": account,
                        "securityId": security,
                        "quantity": quantity,
                    }
                },
            )
        )
        payload = _mutation_payload(data, "createManualHolding")
        mutation_holding = payload.get("holding") or {}
        holding_id = str(mutation_holding.get("id") or "")
        if not holding_id:
            raise APIError("Holding create did not return a holding ID.")
        holding = _read_exact_holding(client, account, holding_id)
        if holding is None:
            raise APIError(
                "Created holding was absent from exact account readback.",
                details={"account_id": account, "holding_id": holding_id},
            )
        _assert_holding_changes(
            holding,
            quantity=quantity,
            cost_basis=None,
            security_type=None,
        )
    output(
        {
            "status": "created",
            "entity": "holding",
            "id": holding_id,
            "account_id": account,
            "security_id": security,
            "verified": True,
            "holding": holding,
        },
        OutputFormat.JSON if json_output else format,
    )


@holding_app.command("update")
@handle_errors
def holding_update_cmd(
    holding_id: Annotated[str, typer.Argument(help="Manual holding ID to update.")],
    account: Annotated[str, typer.Option("--account", help="Containing account ID.")],
    quantity: Annotated[
        float | None,
        typer.Option("--quantity", help="New share/unit quantity."),
    ] = None,
    cost_basis: Annotated[
        float | None,
        typer.Option("--cost-basis", help="New total cost basis."),
    ] = None,
    security_type: Annotated[
        str | None,
        typer.Option("--security-type", help="New holding security type."),
    ] = None,
    format: Annotated[
        OutputFormat | None,
        typer.Option("-f", "--format", help="Output format (plain, json, table, csv, compact)"),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Update a manual holding and verify requested fields by exact readback."""
    if quantity is None and cost_basis is None and security_type is None:
        raise ValidationError(
            "Provide at least one of --quantity, --cost-basis, or --security-type."
        )

    changes: dict[str, Any] = {"id": holding_id}
    if quantity is not None:
        changes["quantity"] = quantity
    if cost_basis is not None:
        changes["costBasis"] = cost_basis
    if security_type is not None:
        changes["securityType"] = security_type

    with spinner("Updating manual holding..."):
        client = get_authenticated_client()
        data = run_api_call(
            lambda: _gql_call(
                client,
                "Common_UpdateHolding",
                _UPDATE_HOLDING_MUTATION,
                {"input": changes},
            )
        )
        _mutation_payload(data, "updateHolding")
        holding = _read_exact_holding(client, account, holding_id)
        if holding is None:
            raise APIError(
                "Updated holding was absent from exact account readback.",
                details={"account_id": account, "holding_id": holding_id},
            )
        _assert_holding_changes(
            holding,
            quantity=quantity,
            cost_basis=cost_basis,
            security_type=security_type,
        )
    output(
        {
            "status": "updated",
            "entity": "holding",
            "id": holding_id,
            "account_id": account,
            "verified": True,
            "holding": holding,
        },
        OutputFormat.JSON if json_output else format,
    )


@holding_app.command("delete")
@handle_errors
def holding_delete_cmd(
    holding_id: Annotated[str, typer.Argument(help="Manual holding ID to delete.")],
    account: Annotated[str, typer.Option("--account", help="Containing account ID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Confirm deletion."),
    ] = False,
    format: Annotated[
        OutputFormat | None,
        typer.Option("-f", "--format", help="Output format (plain, json, table, csv, compact)"),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Delete a manual holding and verify its absence by exact readback."""
    if not yes:
        raise ValidationError("Pass --yes to delete a holding.", field="yes")

    with spinner("Deleting manual holding..."):
        client = get_authenticated_client()
        data = run_api_call(
            lambda: _gql_call(
                client,
                "Common_DeleteHolding",
                _DELETE_HOLDING_MUTATION,
                {"id": holding_id},
            )
        )
        payload = _mutation_payload(data, "deleteHolding")
        if payload.get("deleted") is not True:
            raise APIError(
                "Monarch did not confirm holding deletion.",
                details={"holding_id": holding_id, "response": payload},
            )
        holding = _read_exact_holding(client, account, holding_id)
        if holding is not None:
            raise APIError(
                "Deleted holding remained present after exact account readback.",
                details={"account_id": account, "holding": holding},
            )
    output(
        {
            "status": "deleted",
            "entity": "holding",
            "id": holding_id,
            "verified": True,
        },
        OutputFormat.JSON if json_output else format,
    )
