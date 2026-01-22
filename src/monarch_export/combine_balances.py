from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from monarch_export.export_balances import EXCLUDED_CATEGORIES

TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}")
INCLUDED_ACCOUNTS = {
    "NetWorthAccount",
}


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine Monarch balance exports into a single wide CSV."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory containing Balances_*.csv exports.",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("output/all_balances.csv"),
        help="Output CSV path for the combined balances.",
    )
    parser.add_argument(
        "--plot-file",
        type=Path,
        default=Path("output/total_balances.png"),
        help="Output PNG path for the total balance chart.",
    )
    parser.add_argument(
        "--start-date",
        default="1990-01-01",
        help="Start date for the output series (YYYY-MM-DD).",
    )
    return parser.parse_args(argv)


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def parse_timestamp(name: str, fallback: float) -> dt.datetime:
    match = TIMESTAMP_RE.search(name)
    if match:
        return dt.datetime.strptime(match.group(0), "%Y-%m-%dT%H-%M-%S")
    return dt.datetime.fromtimestamp(fallback)


def read_account_map(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing account map: {path}")
    entries: list[tuple[str, str]] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            account = (row.get("Account") or "").strip()
            category = (row.get("Category") or "").strip()
            if account and category:
                entries.append((account, category))
    return entries


def infer_account_name(path: Path) -> str:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return ""
        normalized = {name.strip().lower(): name for name in reader.fieldnames}
        account_field = normalized.get("account")
        if not account_field:
            return ""
        for row in reader:
            account = (row.get(account_field) or "").strip()
            if account:
                return account
    return ""


def load_balance_rows(path: Path) -> dict[dt.date, str]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return {}
        normalized = {name.strip().lower(): name for name in reader.fieldnames}
        date_field = normalized.get("date")
        balance_field = normalized.get("balance")
        if not date_field or not balance_field:
            return {}
        rows: dict[dt.date, str] = {}
        for row in reader:
            date_raw = (row.get(date_field) or "").strip()
            balance_raw = (row.get(balance_field) or "").strip()
            if not date_raw:
                continue
            try:
                date_value = parse_date(date_raw)
            except ValueError:
                continue
            rows[date_value] = balance_raw
    return rows


def parse_balance(value: str) -> Optional[Decimal]:
    cleaned = value.strip().replace(",", "").replace("$", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def format_decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def select_latest_files(output_dir: Path) -> dict[str, Path]:
    candidates: dict[str, tuple[dt.datetime, Path]] = {}
    for path in output_dir.glob("Balances_*.csv"):
        if not path.is_file():
            continue
        account = infer_account_name(path)
        if not account:
            continue
        timestamp = parse_timestamp(path.name, path.stat().st_mtime)
        existing = candidates.get(account)
        if existing is None or timestamp > existing[0]:
            candidates[account] = (timestamp, path)
    return {account: entry[1] for account, entry in candidates.items()}


def daterange(start: dt.date, end: dt.date) -> list[dt.date]:
    days = (end - start).days
    return [start + dt.timedelta(days=offset) for offset in range(days + 1)]


def run(argv: Optional[Iterable[str]] = None) -> Path:
    args = parse_args(argv)
    output_dir: Path = args.output_dir
    output_path: Path = args.output_file
    plot_path: Path = args.plot_file
    account_map = output_dir / "account_map.csv"

    account_entries = read_account_map(account_map)
    latest_files = select_latest_files(output_dir)

    accounts: list[str] = []
    account_data: dict[str, dict[dt.date, str]] = {}
    for account, category in account_entries:
        if category in EXCLUDED_CATEGORIES and account not in INCLUDED_ACCOUNTS:
            continue
        path = latest_files.get(account)
        if not path:
            continue
        accounts.append(account)
        account_data[account] = load_balance_rows(path)

    start_date = parse_date(args.start_date)
    end_date = dt.date.today()
    dates = daterange(start_date, end_date)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", *accounts, "total"])
        writer.writeheader()
        last_values = {account: "" for account in accounts}
        last_numeric: dict[str, Optional[Decimal]] = {account: None for account in accounts}
        plot_dates: list[dt.date] = []
        plot_totals: list[float] = []
        for current_date in dates:
            row = {"date": current_date.isoformat()}
            total_value = Decimal("0")
            has_total = False
            for account in accounts:
                value = account_data[account].get(current_date)
                if value:
                    last_values[account] = value
                    last_numeric[account] = parse_balance(value)
                row[account] = last_values[account]
                numeric_value = last_numeric[account]
                if numeric_value is not None:
                    total_value += numeric_value
                    has_total = True
            row["total"] = format_decimal(total_value) if has_total else ""
            writer.writerow(row)

            plot_dates.append(current_date)
            plot_totals.append(
                float(total_value) if has_total else float("nan")
            )

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    plot_datetimes = [
        dt.datetime.combine(date, dt.time.min) for date in plot_dates
    ]
    ax.plot(plot_datetimes, plot_totals, color="#1f77b4", linewidth=1.5)
    ax.set_title("Total Balance Over Time")
    ax.set_xlabel("Date")
    ax.set_ylabel("Total Balance")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.grid(True, linewidth=0.4, alpha=0.4)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return output_path


def main(argv: Optional[Iterable[str]] = None) -> None:
    output_path = run(argv)
    print(f"Wrote combined balances to {output_path}")


if __name__ == "__main__":
    main()
