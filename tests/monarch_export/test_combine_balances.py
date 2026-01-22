import csv
import datetime as dt
from pathlib import Path
import sys
import types


def _ensure_matplotlib_stub() -> None:
    try:
        import matplotlib  # noqa: F401
        return
    except Exception:
        pass

    matplotlib = types.ModuleType("matplotlib")
    dates = types.ModuleType("matplotlib.dates")
    pyplot = types.ModuleType("matplotlib.pyplot")

    class DummyLocator:
        pass

    class DummyFormatter:
        def __init__(self, locator):
            self.locator = locator

    class DummyAxis:
        def __init__(self):
            self.locator = DummyLocator()

        def set_major_locator(self, locator):
            self.locator = locator

        def set_major_formatter(self, formatter):
            self.formatter = formatter

        def get_major_locator(self):
            return self.locator

    class DummyAx:
        def __init__(self):
            self.xaxis = DummyAxis()

        def plot(self, *args, **kwargs):
            return []

        def set_title(self, *args, **kwargs):
            pass

        def set_xlabel(self, *args, **kwargs):
            pass

        def set_ylabel(self, *args, **kwargs):
            pass

        def grid(self, *args, **kwargs):
            pass

    class DummyFig:
        def tight_layout(self):
            pass

        def savefig(self, path, dpi=150):
            Path(path).write_bytes(b"stub")

    def subplots(*args, **kwargs):
        return DummyFig(), DummyAx()

    def close(fig):
        return None

    dates.AutoDateLocator = DummyLocator
    dates.ConciseDateFormatter = DummyFormatter
    pyplot.subplots = subplots
    pyplot.close = close

    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.dates"] = dates
    sys.modules["matplotlib.pyplot"] = pyplot


_ensure_matplotlib_stub()


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

from monarch_export import combine_balances


def write_balance_csv(path: Path, account: str, rows: list[tuple[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Balance", "Account"])
        writer.writeheader()
        for date_value, balance_value in rows:
            writer.writerow(
                {"Date": date_value, "Balance": balance_value, "Account": account}
            )


def test_parse_timestamp_reads_from_filename():
    timestamp = combine_balances.parse_timestamp(
        "Balances_cash-checking-2024-01-02T03-04-05.csv", 0
    )
    assert timestamp == dt.datetime(2024, 1, 2, 3, 4, 5)


def test_read_account_map_extracts_accounts(tmp_path: Path):
    account_map = tmp_path / "account_map.csv"
    account_map.write_text(
        "Account,Category\nChecking,Cash\nInvestments,Investments\n",
        encoding="utf-8",
    )

    entries = combine_balances.read_account_map(account_map)
    assert entries == [("Checking", "Cash"), ("Investments", "Investments")]


def test_infer_account_name_reads_first_account(tmp_path: Path):
    path = tmp_path / "Balances_cash-checking.csv"
    path.write_text(
        "Date,Balance,Account\n2024-01-01,1000,\n2024-01-02,1050,Checking\n",
        encoding="utf-8",
    )

    assert combine_balances.infer_account_name(path) == "Checking"


def test_load_balance_rows_skips_invalid_rows(tmp_path: Path):
    path = tmp_path / "Balances_cash-checking.csv"
    path.write_text(
        "Date,Balance,Account\n"
        "invalid,1000,Checking\n"
        "2024-01-02,1050,Checking\n",
        encoding="utf-8",
    )

    rows = combine_balances.load_balance_rows(path)
    assert rows == {dt.date(2024, 1, 2): "1050"}


def test_parse_balance_and_format_decimal():
    value = combine_balances.parse_balance("$1,234.567")
    assert value == combine_balances.Decimal("1234.567")
    assert combine_balances.format_decimal(value) == "1234.57"
    assert combine_balances.parse_balance("abc") is None


def test_select_latest_files_prefers_newest_timestamp(tmp_path: Path):
    first = tmp_path / "Balances_cash-checking-2024-01-01T00-00-00.csv"
    second = tmp_path / "Balances_cash-checking-2024-02-01T00-00-00.csv"

    write_balance_csv(first, "Checking", [("2024-01-01", "100")])
    write_balance_csv(second, "Checking", [("2024-02-01", "200")])

    selected = combine_balances.select_latest_files(tmp_path)
    assert selected == {"Checking": second}


def test_run_combines_balances_and_writes_plot(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    account_map = output_dir / "account_map.csv"
    account_map.write_text(
        "Account,Type,Category,URL\n"
        "Checking,,Cash,https://example.com/1\n"
        "Visa,,Credit Cards,https://example.com/2\n",
        encoding="utf-8",
    )

    today = dt.date.today()
    today_str = today.isoformat()

    write_balance_csv(
        output_dir / f"Balances_cash-checking-{today_str}T00-00-00.csv",
        "Checking",
        [(today_str, "1000.50")],
    )
    write_balance_csv(
        output_dir / f"Balances_credit_cards-visa-{today_str}T00-00-00.csv",
        "Visa",
        [(today_str, "500.00")],
    )

    output_file = tmp_path / "all_balances.csv"
    plot_file = tmp_path / "total_balances.png"

    result = combine_balances.run(
        [
            "--output-dir",
            str(output_dir),
            "--output-file",
            str(output_file),
            "--plot-file",
            str(plot_file),
            "--start-date",
            today_str,
        ]
    )

    assert result == output_file
    assert output_file.exists()
    assert plot_file.exists()

    with output_file.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == ["date", "Checking", "total"]
    assert rows == [
        {"date": today_str, "Checking": "1000.50", "total": "1000.50"}
    ]


def test_run_includes_allowlisted_other_account(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    account_map = output_dir / "account_map.csv"
    account_map.write_text(
        "Account,Type,Category,URL\n"
        "Checking,,Cash,https://example.com/1\n"
        "NetWorthAccount,,Other,https://example.com/2\n"
        "Rewards,,Other,https://example.com/3\n",
        encoding="utf-8",
    )

    today = dt.date.today()
    today_str = today.isoformat()

    write_balance_csv(
        output_dir / f"Balances_cash-checking-{today_str}T00-00-00.csv",
        "Checking",
        [(today_str, "1000.50")],
    )
    write_balance_csv(
        output_dir / f"Balances_other-networth-{today_str}T00-00-00.csv",
        "NetWorthAccount",
        [(today_str, "250.00")],
    )
    write_balance_csv(
        output_dir / f"Balances_other-rewards-{today_str}T00-00-00.csv",
        "Rewards",
        [(today_str, "15.00")],
    )

    output_file = tmp_path / "all_balances.csv"
    plot_file = tmp_path / "total_balances.png"

    result = combine_balances.run(
        [
            "--output-dir",
            str(output_dir),
            "--output-file",
            str(output_file),
            "--plot-file",
            str(plot_file),
            "--start-date",
            today_str,
        ]
    )

    assert result == output_file
    assert output_file.exists()
    assert plot_file.exists()

    with output_file.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == ["date", "Checking", "NetWorthAccount", "total"]
    assert rows == [
        {
            "date": today_str,
            "Checking": "1000.50",
            "NetWorthAccount": "250.00",
            "total": "1250.50",
        }
    ]
