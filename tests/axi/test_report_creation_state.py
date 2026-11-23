"""Report creation no-ops require complete state and no unrequested filters."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from monarch_cli.core.report_api import create_report
from monarch_cli.core.report_config import (
    BOOL_FILTERS,
    DATE_FILTERS,
    LIST_FILTERS,
    NUMBER_FILTERS,
    STRING_FILTERS,
    VIEW_FIELDS,
    build_create_input,
)
from monarch_cli.core.report_state import native_filter_name


def saved():
    spec = build_create_input("Example")
    keys = (
        BOOL_FILTERS
        | DATE_FILTERS
        | LIST_FILTERS
        | NUMBER_FILTERS
        | STRING_FILTERS
        | {"timeframePeriod"}
    )
    filters = {native_filter_name(k): None for k in keys}
    filters.update(
        hiddenFromReports=False,
        tagMatchMode="any",
        excludeTagMatchMode="any",
        systemCategories=None,
        systemCategoryGroups=None,
        ownershipSet=None,
        businessEntitySet=None,
    )
    return {
        "id": "r1",
        "displayName": "Example",
        "transactionFilterSet": filters,
        "reportView": {**dict.fromkeys(VIEW_FIELDS), **spec["reportView"]},
    }


async def test_complete_matching_report_noop_without_write():
    client = MagicMock(gql_call=AsyncMock(return_value={"reportConfigurations": [saved()]}))
    result = await create_report(client, build_create_input("Example"))
    assert result["status"] == "unchanged" and result["verified"] is True
    assert client.gql_call.await_count == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("isPending", False),
        ("accounts", [{"id": "a1"}]),
        ("absAmountLte", 0),
        ("ownershipSet", {"users": [{"id": "u1"}]}),
    ],
)
async def test_extra_filters_never_confirm_requested_state(field, value):
    from monarch_cli.core.exceptions import ValidationError

    row = saved()
    row["transactionFilterSet"][field] = value
    client = MagicMock(gql_call=AsyncMock(return_value={"reportConfigurations": [row]}))
    with pytest.raises(ValidationError):
        await create_report(client, build_create_input("Example"))
    assert client.gql_call.await_count == 1


async def test_invalid_calculation_does_not_become_default():
    from monarch_cli.core.exceptions import ValidationError

    row = saved()
    row["reportView"]["chartCalculation"] = False
    client = MagicMock(gql_call=AsyncMock(return_value={"reportConfigurations": [row]}))
    with pytest.raises(ValidationError):
        await create_report(client, build_create_input("Example"))
    assert client.gql_call.await_count == 1


async def test_missing_filter_cannot_prove_equivalence():
    from monarch_cli.core.exceptions import ValidationError

    row = saved()
    del row["transactionFilterSet"]["hasNotes"]
    client = MagicMock(gql_call=AsyncMock(return_value={"reportConfigurations": [row]}))
    with pytest.raises(ValidationError):
        await create_report(client, build_create_input("Example"))
    assert client.gql_call.await_count == 1


async def test_error_envelope_cannot_establish_report_absence():
    from monarch_cli.core.exceptions import APIError

    client = MagicMock(
        gql_call=AsyncMock(return_value={"reportConfigurations": [], "errors": ["failed"]})
    )
    with pytest.raises(APIError):
        await create_report(client, build_create_input("Example"))
    assert client.gql_call.await_count == 1


async def test_conflicting_state_has_exact_inspection_hint():
    from monarch_cli.core.exceptions import ValidationError

    row = saved()
    row["transactionFilterSet"]["isPending"] = True
    client = MagicMock(gql_call=AsyncMock(return_value={"reportConfigurations": [row]}))
    with pytest.raises(ValidationError) as error:
        await create_report(client, build_create_input("Example"))
    assert error.value.details["fix"] == "monarch report show r1"


def test_cli_matching_report_returns_verified_unchanged_json():
    import json
    from unittest.mock import patch

    from typer.testing import CliRunner

    from monarch_cli.main import app

    client = MagicMock(gql_call=AsyncMock(return_value={"reportConfigurations": [saved()]}))
    with patch("monarch_cli.commands.report.get_authenticated_client", return_value=client):
        result = CliRunner().invoke(app, ["report", "create", "--name", "Example", "--json"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["status"] == "unchanged"
    assert json.loads(result.stdout)["verified"] is True
    assert client.gql_call.await_count == 1
