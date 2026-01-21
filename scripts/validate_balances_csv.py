import argparse
import csv
import sys
from pathlib import Path


def parse_args() -> Path:
    parser = argparse.ArgumentParser(description="Validate a balances CSV export.")
    parser.add_argument("csv_path", type=Path, help="Path to a balances CSV file.")
    args = parser.parse_args()
    return args.csv_path


def main() -> int:
    csv_path = parse_args()
    if not csv_path.exists():
        print(f"File not found: {csv_path}", file=sys.stderr)
        return 2

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            print("Missing header row.", file=sys.stderr)
            return 2
        required = {"date", "balance", "account"}
        normalized = {name.strip().lower(): name for name in reader.fieldnames}
        if not required.issubset(normalized.keys()):
            print(
                f"Missing required columns: {sorted(required)}; "
                f"found {reader.fieldnames}.",
                file=sys.stderr,
            )
            return 2

        total_rows = 0
        empty_rows = 0
        for row in reader:
            total_rows += 1
            if not row[normalized["date"]].strip():
                empty_rows += 1
            if not row[normalized["balance"]].strip():
                empty_rows += 1
            if not row[normalized["account"]].strip():
                empty_rows += 1

    print(f"Rows: {total_rows}")
    if empty_rows:
        print(f"Empty fields: {empty_rows}")
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
