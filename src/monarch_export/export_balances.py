from __future__ import annotations

import argparse
import csv
import re
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ACCOUNTS_URL = "https://app.monarch.com/accounts"

BALANCES_FILENAME_RE = re.compile(
    r"Balances_(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.csv"
)
INVALID_ACCOUNT_NAMES = {
    "accounts",
    "set credit limit",
}

CATEGORY_INVESTMENTS = "Investments"
CATEGORY_OTHER = "Other"
CATEGORY_CASH = "Cash"
CATEGORY_CREDIT_CARDS = "Credit Cards"
CATEGORY_REAL_ESTATE = "Real Estate"
CATEGORY_LOANS = "Loans"
CATEGORY_OTHER_ASSETS = "Other Assets"
EXCLUDED_CATEGORIES = {
    CATEGORY_CREDIT_CARDS,
    CATEGORY_OTHER,
}


@dataclass(frozen=True)
class AccountInfo:
    name: str
    url: str
    type_label: str
    category: str


@dataclass(frozen=True)
class ExportConfig:
    user_data_dir: Path
    profile_directory: str
    output_dir: Path
    channel: str
    headless: bool
    manual: bool
    cdp_url: Optional[str]
    skip_existing: bool


def parse_args(argv: Optional[Iterable[str]] = None) -> ExportConfig:
    parser = argparse.ArgumentParser(
        description="Export Monarch Money account balances to CSV."
    )
    parser.add_argument(
        "--user-data-dir",
        type=Path,
        default=Path.home() / "Library/Application Support/Google/Chrome",
        help="Chrome user data directory to reuse the logged-in session.",
    )
    parser.add_argument(
        "--profile-directory",
        default="Default",
        help="Chrome profile directory name inside the user data dir.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to write exported CSV files.",
    )
    parser.add_argument(
        "--channel",
        default="chrome",
        help="Browser channel for Playwright (default: chrome).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (not recommended for manual export).",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Skip auto-click and wait for you to trigger the export manually.",
    )
    parser.add_argument(
        "--cdp-url",
        help=(
            "Connect to an existing Chrome session via remote debugging "
            "(e.g., http://localhost:9222)."
        ),
    )
    parser.add_argument(
        "--cdp-port",
        type=int,
        help="Shortcut for --cdp-url http://localhost:<port>.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip accounts that already have exports in the output directory.",
    )
    args = parser.parse_args(argv)
    if args.cdp_url and args.cdp_port:
        parser.error("Use either --cdp-url or --cdp-port, not both.")
    cdp_url = args.cdp_url
    if args.cdp_port:
        cdp_url = f"http://localhost:{args.cdp_port}"
    return ExportConfig(
        user_data_dir=args.user_data_dir,
        profile_directory=args.profile_directory,
        output_dir=args.output_dir,
        channel=args.channel,
        headless=args.headless,
        manual=args.manual,
        cdp_url=cdp_url,
        skip_existing=args.skip_existing,
    )


def is_login_page(url: str) -> bool:
    lowered = url.lower()
    return "login" in lowered or "sign-in" in lowered or "auth" in lowered


def ensure_logged_in(page) -> None:
    if not is_login_page(page.url):
        return
    print(
        "Monarch login required. Please sign in within the opened browser, "
        "then press Enter here to continue.",
        flush=True,
    )
    input()
    page.wait_for_load_state("domcontentloaded")
    if is_login_page(page.url):
        raise RuntimeError(
            "Still on login page after waiting. Log in first, then rerun."
        )


def extract_account_fields(candidate_text: str) -> tuple[str, str]:
    lines = [line.strip() for line in candidate_text.splitlines() if line.strip()]
    name = ""
    type_label = ""
    for line in lines:
        if not name and re.search(r"[A-Za-z0-9]", line):
            name = line
            continue
        if name and not type_label:
            lowered = line.lower()
            if "$" in line or "ago" in lowered or "shared" in lowered:
                continue
            if re.search(r"[A-Za-z0-9]", line):
                type_label = line
                break
    return name, type_label


def fetch_accounts(page) -> list[AccountInfo]:
    page.goto(ACCOUNTS_URL, wait_until="domcontentloaded")
    ensure_logged_in(page)
    page.wait_for_timeout(1500)
    try:
        page.wait_for_selector("a[href*='/accounts/']", timeout=10000)
    except PlaywrightTimeoutError:
        pass

    category_labels = [
        CATEGORY_INVESTMENTS,
        CATEGORY_OTHER,
        CATEGORY_CASH,
        CATEGORY_CREDIT_CARDS,
        CATEGORY_REAL_ESTATE,
        CATEGORY_LOANS,
        CATEGORY_OTHER_ASSETS,
    ]

    raw_accounts = page.evaluate(
        """
        (categories) => {
          const normalize = (text) => (text || '').trim().replace(/\\s+/g, ' ');
          const categoryLabels = categories.slice();
          const anchors = Array.from(document.querySelectorAll(\"a[href*='/accounts/']\"));

          const categoryFromText = (text) => {
            const normalized = normalize(text);
            if (!normalized) return '';
            const cleaned = normalized.replace(/^[^A-Za-z]+/, '');
            const lowered = cleaned.toLowerCase();
            for (const cat of categoryLabels) {
              if (lowered.startsWith(cat.toLowerCase())) {
                return cat;
              }
            }
            return '';
          };

          const findCard = (el) => {
            let node = el;
            while (node) {
              const className = (node.className || '').toString();
              if (
                className.includes('AccountGroupCard__Root') ||
                className.includes('AccountGroupCard__CustomCard')
              ) {
                return node;
              }
              node = node.parentElement;
            }
            return null;
          };

          const findCategory = (anchor) => {
            const card = findCard(anchor);
            if (!card) return '';
            const header =
              card.querySelector('[class*=\"AccountGroupCard__Header\"]') ||
              card.querySelector('[class*=\"AccountGroupCard__Content\"]') ||
              card.querySelector('[class*=\"AccountGroupCard__ColumnWhenSmall\"]');
            const headerText = header ? header.innerText : '';
            let category = categoryFromText(headerText);
            if (category) return category;
            category = categoryFromText(card.innerText);
            return category;
          };

          return anchors
            .map((el) => {
              const href = el.href || '';
              if (!href) return null;
              const url = new URL(href);
              const parts = url.pathname.split('/').filter(Boolean);
              if (parts.length < 2 || parts[0] !== 'accounts') return null;
              if (parts[1] === 'details' && parts.length < 3) return null;
              const text = el.innerText || '';
              const label =
                (el.getAttribute('aria-label') || '').trim() ||
                (el.getAttribute('title') || '').trim();
              return {
                href,
                text,
                label,
                category: findCategory(el),
              };
            })
            .filter(Boolean);
        }
        """,
        category_labels,
    )

    seen = set()
    accounts: list[AccountInfo] = []
    for entry in raw_accounts:
        href = entry.get("href", "")
        if not href:
            continue
        parsed = urlparse(href)
        parts = [part for part in (parsed.path or "").split("/") if part]
        if len(parts) < 2 or parts[0] != "accounts":
            continue
        if parts[1] == "details":
            if len(parts) < 3:
                continue
            account_id = parts[2]
            canonical_url = (
                f"{parsed.scheme}://{parsed.netloc}/accounts/details/{account_id}"
            )
        else:
            account_id = parts[1]
            canonical_url = f"{parsed.scheme}://{parsed.netloc}/accounts/{account_id}"
        if canonical_url in seen:
            continue
        seen.add(canonical_url)
        candidate_text = entry.get("label") or entry.get("text") or ""
        name, type_label = extract_account_fields(candidate_text)
        if (
            not name
            or not re.search(r"[A-Za-z0-9]", name)
            or name.strip().lower() in INVALID_ACCOUNT_NAMES
        ):
            continue
        category = entry.get("category", "").strip()
        if not category:
            category = CATEGORY_OTHER
            print(
                f"Warning: no heading found for {name}; defaulting to {category}.",
                flush=True,
            )
        accounts.append(
            AccountInfo(
                name=name,
                url=canonical_url,
                type_label=type_label,
                category=category,
            )
        )

    if not accounts:
        raise RuntimeError(
            "No accounts found on the Accounts page. "
            "Open Monarch and ensure account links are visible."
        )
    return accounts


def print_accounts(accounts: list[AccountInfo]) -> None:
    print("Accounts found:", flush=True)
    for idx, account in enumerate(accounts, start=1):
        type_suffix = ""
        if account.type_label and account.type_label != account.category:
            type_suffix = f" ({account.type_label})"
        print(
            f"{idx}. {account.name} [{account.category}]{type_suffix}",
            flush=True,
        )


def dismiss_cookie_banner(page) -> None:
    for label in ("Accept", "Deny Non-Essential"):
        locator = page.get_by_role("button", name=label)
        if locator.count():
            try:
                locator.first.click()
            except Exception:
                pass
            break


def click_edit_dropdown(page) -> bool:
    buttons = page.locator("button")
    count = buttons.count()
    candidates = []
    for idx in range(count):
        btn = buttons.nth(idx)
        try:
            text = btn.inner_text().strip()
        except Exception:
            continue
        if not text:
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            continue
        normalized = " ".join(lines)
        words = re.findall(r"[A-Za-z]+", normalized)
        if not words or [word.lower() for word in words] != ["edit"]:
            continue
        candidates.append(btn)

    menu_locator = page.get_by_text(
        re.compile(r"download balance history", re.I)
    )
    for btn in candidates:
        try:
            btn.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            btn.click()
        except Exception:
            continue
        try:
            menu_locator.first.wait_for(state="visible", timeout=2000)
            return True
        except Exception:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
    return False


def open_account_menu(page) -> bool:
    dismiss_cookie_banner(page)
    try:
        page.wait_for_selector("button:has-text('Edit')", timeout=5000)
    except Exception:
        pass
    try:
        page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass
    if click_edit_dropdown(page):
        return True
    def click_non_multiple(locator) -> bool:
        if locator.count() == 0:
            return False
        candidate = locator.first
        try:
            text = candidate.inner_text().strip().lower()
        except Exception:
            text = ""
        if "multiple" in text:
            return False
        try:
            candidate.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            candidate.click()
            return True
        except Exception:
            return False

    candidates = [
        page.get_by_role("button", name=re.compile(r"^edit$", re.I)),
        page.get_by_role("button", name=re.compile(r"edit", re.I)),
        page.get_by_role("button", name=re.compile(r"more|actions|options", re.I)),
        page.locator(
            "button[aria-label*='More'], button[aria-label*='Actions'], "
            "button[aria-label*='Options'], button[aria-label*='Account']"
        ),
    ]
    for locator in candidates:
        if click_non_multiple(locator):
            return True
    return False


def trigger_account_download(page) -> Optional[object]:
    download_targets = [
        page.get_by_role(
            "menuitem", name=re.compile(r"download balance history", re.I)
        ),
        page.get_by_text(re.compile(r"download balance history", re.I)),
        page.get_by_role(
            "menuitem", name=re.compile(r"download.*balances?", re.I)
        ),
        page.get_by_role("menuitem", name=re.compile(r"download.*balance", re.I)),
        page.get_by_role("menuitem", name=re.compile(r"balance", re.I)),
        page.get_by_role("button", name=re.compile(r"download.*balance", re.I)),
    ]

    def try_click(locator) -> Optional[object]:
        if locator.count() == 0:
            return None
        try:
            locator.first.wait_for(state="visible", timeout=2000)
        except Exception:
            pass
        try:
            locator.first.scroll_into_view_if_needed()
        except Exception:
            pass
        with page.expect_download(timeout=15000) as download_info:
            locator.first.click()
        return download_info.value

    for attempt in range(3):
        menu_opened = open_account_menu(page)
        if menu_opened:
            page.wait_for_timeout(1200)
            try:
                page.wait_for_selector(
                    "div[role='menuitem'] >> text=/download balance history/i",
                    timeout=4000,
                )
            except Exception:
                pass

        for locator in download_targets:
            download = try_click(locator)
            if download is not None:
                return download

        if menu_opened:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
        page.wait_for_timeout(800)
    return None


def wait_for_manual_download(page, account_name: str) -> object:
    print(
        f"Manual step needed for {account_name}. Press Enter here, then open the "
        "account menu and click 'Download balance history'.",
        flush=True,
    )
    input()
    return page.wait_for_event("download", timeout=120000)


def sanitize_balance(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    value = value.replace("$", "").replace(",", "")
    return value


def clean_csv(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV is missing a header row.")
        required = {"date", "balance", "account"}
        normalized = {name.strip().lower(): name for name in reader.fieldnames}
        if not required.issubset(normalized.keys()):
            raise ValueError(
                f"CSV missing required columns {sorted(required)}; "
                f"found {reader.fieldnames}."
            )
        rows = []
        for row in reader:
            rows.append(
                {
                    "Date": row[normalized["date"]].strip(),
                    "Balance": sanitize_balance(row[normalized["balance"]]),
                    "Account": row[normalized["account"]].strip(),
                }
            )

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Date", "Balance", "Account"])
        writer.writeheader()
        writer.writerows(rows)


def slugify_account(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name.strip())
    return slug.strip("_").lower()


def slugify_category(category: str) -> str:
    return slugify_account(category) or "other"


def account_has_export(output_dir: Path, account: AccountInfo) -> bool:
    slug = slugify_account(account.name)
    if not slug:
        return False
    category = slugify_category(account.category)
    return bool(
        list(output_dir.glob(f"Balances_{category}-{slug}-*.csv"))
        or list(output_dir.glob(f"Balances_*-{slug}-*.csv"))
        or list(output_dir.glob(f"Balances_{category}_{slug}_*.csv"))
        or list(output_dir.glob(f"Balances_*_{slug}_*.csv"))
    )


def resolve_account_output_path(
    output_dir: Path,
    suggested_name: str,
    account_name: str,
    index: int,
    category: str,
) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    match = BALANCES_FILENAME_RE.fullmatch(suggested_name)
    if match:
        timestamp = match.group("timestamp")
    safe_account = slugify_account(account_name) or f"account_{index}"
    safe_category = slugify_category(category)
    return output_dir / f"Balances_{safe_category}-{safe_account}-{timestamp}.csv"


def write_account_map(output_dir: Path, accounts: list[AccountInfo]) -> Path:
    output_path = output_dir / "account_map.csv"
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["Account", "Type", "Category", "URL"]
        )
        writer.writeheader()
        for account in accounts:
            writer.writerow(
                {
                    "Account": account.name,
                    "Type": account.type_label,
                    "Category": account.category,
                    "URL": account.url,
                }
            )
    return output_path


def run_export(config: ExportConfig) -> Path:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    temp_path = config.output_dir / ".balances_download.csv"

    with sync_playwright() as playwright:
        print("Launching browser context...", flush=True)
        browser = None
        context = None
        opened_page = None
        if config.cdp_url:
            browser = playwright.chromium.connect_over_cdp(config.cdp_url)
            if not browser.contexts:
                raise RuntimeError(
                    "No browser contexts detected. Ensure Chrome is running "
                    "with remote debugging enabled."
                )
            context = browser.contexts[0]
        else:
            try:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(config.user_data_dir),
                    channel=config.channel,
                    headless=config.headless,
                    args=[f"--profile-directory={config.profile_directory}"],
                )
            except Exception as exc:
                message = (
                    "Failed to launch Chromium with the requested profile. "
                    "Close any running Chrome windows using that profile and "
                    "try again."
                )
                if "ProcessSingleton" in str(exc) or "SingletonLock" in str(exc):
                    message = (
                        "Chrome is already running with this profile. Close "
                        "Chrome and rerun, or start Chrome with remote "
                        "debugging and pass --cdp-url."
                    )
                raise RuntimeError(message) from exc
        print("Browser context ready.", flush=True)

        try:
            page = context.pages[0] if context.pages else context.new_page()
            opened_page = page
            print("Loading Monarch accounts list...", flush=True)
            accounts = fetch_accounts(page)
            print_accounts(accounts)
            write_account_map(config.output_dir, accounts)

            output_paths: list[Path] = []
            errors: list[str] = []
            handled = 0
            for idx, account in enumerate(accounts, start=1):
                print(
                    f"Exporting {idx}/{len(accounts)}: {account.name}",
                    flush=True,
                )
                if account.category in EXCLUDED_CATEGORIES:
                    print(
                        f"Skipping {account.name}; {account.category} balances are excluded.",
                        flush=True,
                    )
                    handled += 1
                    print(
                        f"Handled {handled}/{len(accounts)} accounts.",
                        flush=True,
                    )
                    continue
                if config.skip_existing and account_has_export(
                    config.output_dir, account
                ):
                    print(f"Skipping {account.name}; export already exists.", flush=True)
                    handled += 1
                    print(
                        f"Handled {handled}/{len(accounts)} accounts.",
                        flush=True,
                    )
                    continue
                try:
                    page.goto(account.url, wait_until="domcontentloaded")
                    ensure_logged_in(page)
                    try:
                        page.wait_for_selector("text=Current Balance", timeout=10000)
                    except Exception:
                        pass

                    download = None
                    if not config.manual:
                        try:
                            download = trigger_account_download(page)
                        except PlaywrightTimeoutError:
                            download = None

                    if download is None:
                        download = wait_for_manual_download(page, account.name)

                    suggested_name = download.suggested_filename
                    output_path = resolve_account_output_path(
                        config.output_dir,
                        suggested_name,
                        account.name,
                        idx,
                        account.category,
                    )
                    download.save_as(str(temp_path))
                    clean_csv(temp_path, output_path)
                    temp_path.unlink(missing_ok=True)
                    output_paths.append(output_path)
                    print(f"Wrote {account.name} balances to {output_path}")
                    handled += 1
                    print(
                        f"Handled {handled}/{len(accounts)} accounts.",
                        flush=True,
                    )
                except Exception as exc:
                    errors.append(f"{account.name}: {exc}")

            if errors:
                raise RuntimeError("One or more accounts failed:\n" + "\n".join(errors))
            if output_paths:
                return output_paths[-1]
        finally:
            if opened_page and opened_page.is_closed() is False:
                try:
                    opened_page.close()
                except Exception:
                    pass
            if context and not config.cdp_url:
                context.close()
    raise RuntimeError("Export did not produce an output file.")


def main(argv: Optional[Iterable[str]] = None) -> None:
    config = parse_args(argv)
    output_path = run_export(config)
    print(f"Wrote balances CSV to {output_path}")


if __name__ == "__main__":
    main()
