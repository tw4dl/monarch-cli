import csv
from pathlib import Path
import sys
import types

import pytest


def _ensure_playwright_stub() -> None:
    try:
        import playwright.sync_api  # noqa: F401
        return
    except Exception:
        pass

    playwright = types.ModuleType("playwright")
    sync_api = types.ModuleType("playwright.sync_api")

    class DummyTimeoutError(Exception):
        pass

    def sync_playwright():
        raise RuntimeError("playwright is not available in this environment")

    sync_api.TimeoutError = DummyTimeoutError
    sync_api.sync_playwright = sync_playwright
    sys.modules["playwright"] = playwright
    sys.modules["playwright.sync_api"] = sync_api


_ensure_playwright_stub()

from monarch_export import export_balances


def test_parse_args_conflict_cdp_options():
    with pytest.raises(SystemExit):
        export_balances.parse_args(
            ["--cdp-url", "http://localhost:9222", "--cdp-port", "9222"]
        )


def test_parse_args_cdp_port_sets_url():
    config = export_balances.parse_args(["--cdp-port", "9222"])
    assert config.cdp_url == "http://localhost:9222"


def test_is_login_page_detects_login_variants():
    assert export_balances.is_login_page("https://app.monarch.com/login")
    assert export_balances.is_login_page("https://app.monarch.com/sign-in")
    assert export_balances.is_login_page("https://app.monarch.com/auth/callback")
    assert not export_balances.is_login_page("https://app.monarch.com/accounts")


def test_extract_account_fields_skips_balance_and_shared_lines():
    candidate = "My Checking Account\n$1,234.00\nShared by Alex\nChecking"
    name, type_label = export_balances.extract_account_fields(candidate)
    assert name == "My Checking Account"
    assert type_label == "Checking"


def test_sanitize_balance_removes_commas_and_currency():
    assert export_balances.sanitize_balance("$1,234.56") == "1234.56"
    assert export_balances.sanitize_balance("  ") == ""


def test_clean_csv_normalizes_headers_and_sanitizes_values(tmp_path: Path):
    input_path = tmp_path / "raw.csv"
    output_path = tmp_path / "clean.csv"
    with input_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["DATE", "Balance", "Account"])
        writer.writerow(["2024-01-01", "$1,234.56", "Checking"])

    export_balances.clean_csv(input_path, output_path)

    with output_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == ["Date", "Balance", "Account"]
    assert rows == [
        {"Date": "2024-01-01", "Balance": "1234.56", "Account": "Checking"}
    ]


def test_clean_csv_requires_expected_columns(tmp_path: Path):
    input_path = tmp_path / "bad.csv"
    output_path = tmp_path / "clean.csv"
    input_path.write_text("Date,Balance\n2024-01-01,100\n", encoding="utf-8")

    with pytest.raises(ValueError):
        export_balances.clean_csv(input_path, output_path)


def test_slugify_helpers():
    assert export_balances.slugify_account("My Checking") == "my_checking"
    assert export_balances.slugify_account("  ") == ""
    assert export_balances.slugify_category("") == "other"


def test_account_has_export_matches_variants(tmp_path: Path):
    account = export_balances.AccountInfo(
        name="My Checking",
        url="https://example.com/accounts/1",
        type_label="",
        category="Cash",
    )
    first = tmp_path / "Balances_cash-my_checking-2024-01-01T00-00-00.csv"
    first.write_text("stub", encoding="utf-8")
    assert export_balances.account_has_export(tmp_path, account)

    second_account = export_balances.AccountInfo(
        name="My Savings",
        url="https://example.com/accounts/2",
        type_label="",
        category="Cash",
    )
    assert not export_balances.account_has_export(tmp_path, second_account)


def test_resolve_account_output_path_uses_suggested_timestamp(tmp_path: Path):
    path = export_balances.resolve_account_output_path(
        tmp_path,
        "Balances_2024-02-03T04-05-06.csv",
        "My Checking",
        1,
        "Cash",
    )
    assert path.name == "Balances_cash-my_checking-2024-02-03T04-05-06.csv"
