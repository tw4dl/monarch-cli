"""Validate a single account's balance-history CSV before loading credentials."""

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from pathlib import Path

from .adapter import BalanceHistoryRow
from .exceptions import ValidationError


def read_balance_history_csv(path: Path) -> list[BalanceHistoryRow]:
    rows: list[BalanceHistoryRow] = []
    dates: set[datetime] = set()
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, strict=True)
            headers = [name.strip().lower().replace(" ", "_") for name in reader.fieldnames or []]
            if len(headers) != len(set(headers)) or not all(headers):
                raise ValueError("CSV headers must be nonempty and unique.")
            amount_fields = set(headers) & {"amount", "balance"}
            if "date" not in headers or len(amount_fields) != 1:
                raise ValueError("CSV requires date and exactly one amount or balance column.")
            amount_field = next(iter(amount_fields))
            for index, raw in enumerate(reader, start=2):
                if None in raw:
                    raise ValueError(f"CSV row {index} has extra values.")
                row = {name.strip().lower().replace(" ", "_"): value for name, value in raw.items()}
                date_text = (row.get("date") or "").strip()
                try:
                    day = datetime.fromisoformat(date_text)
                    if day.strftime("%Y-%m-%d") != date_text:
                        raise ValueError
                    amount = Decimal((row.get(amount_field) or "").strip())
                    if not amount.is_finite() or not isfinite(float(amount)):
                        raise ValueError
                except (ValueError, InvalidOperation, OverflowError) as exc:
                    raise ValueError(
                        f"CSV row {index} requires YYYY-MM-DD and a finite numeric amount."
                    ) from exc
                if day in dates:
                    raise ValueError(f"CSV row {index} repeats a date.")
                dates.add(day)
                rows.append(
                    BalanceHistoryRow(
                        date=day, amount=float(amount), account_name=row.get("account_name")
                    )
                )
        if not rows:
            raise ValueError("CSV must contain at least one balance row.")
    except (ValueError, UnicodeError, csv.Error) as exc:
        raise ValidationError(str(exc), field="csv_path") from exc
    return rows
