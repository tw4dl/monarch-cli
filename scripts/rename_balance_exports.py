import csv
import re
from pathlib import Path


BALANCES_FILENAME_RE = re.compile(
    r"Balances_(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.csv"
)


def slugify_account(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name.strip())
    return slug.strip("_").lower()


def slugify_category(name: str) -> str:
    return slugify_account(name) or "other"


def load_account_categories(output_dir: Path) -> dict[str, str]:
    account_map_path = output_dir / "account_map.csv"
    if not account_map_path.exists():
        return {}
    categories: dict[str, str] = {}
    with account_map_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            account = (row.get("Account") or "").strip()
            category = (row.get("Category") or "").strip()
            if account and category and account not in categories:
                categories[account] = category
    return categories


def infer_account_name(csv_path: Path) -> str:
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            account = (row.get("Account") or "").strip()
            if account:
                return account
    return ""


def main() -> None:
    output_dir = Path("output")
    account_categories = load_account_categories(output_dir)
    renamed = 0
    for path in output_dir.glob("Balances_*.csv"):
        match = BALANCES_FILENAME_RE.fullmatch(path.name)
        if not match:
            continue
        account = infer_account_name(path)
        if not account:
            continue
        slug = slugify_account(account)
        if not slug:
            continue
        category = slugify_category(account_categories.get(account, "Other"))
        timestamp = match.group("timestamp")
        new_path = path.with_name(f"Balances_{category}-{slug}-{timestamp}.csv")
        if new_path.exists():
            continue
        path.rename(new_path)
        renamed += 1
    print(f"Renamed {renamed} files.")


if __name__ == "__main__":
    main()
