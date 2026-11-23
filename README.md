# Monarch CLI

[![PyPI version](https://badge.fury.io/py/monarch-cli.svg)](https://badge.fury.io/py/monarch-cli)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A command-line interface for [Monarch Money](https://www.monarchmoney.com/), a personal finance platform that helps you track spending, manage budgets, and monitor your net worth across all your accounts in one place.

> **Disclaimer:** This is an unofficial, community-maintained project and is not affiliated with, endorsed by, or connected to Monarch Money in any way.

## Features

- 🔐 **Secure authentication** with session persistence (keyring or file storage)
- 📊 **Multiple output formats** (TOON, plain, JSON, table, CSV) for flexible processing
- 🔧 **Scriptable** - explicit JSON output with `--json`; compact TOON by default
- 📅 **Smart date presets** (`--preset this-month`, `--preset ytd`)
- ✏️ **Transaction updates** with dry-run preview support
- 🔄 **Account refresh** to sync latest data from institutions

## Installation

### With pip

```bash
pip install monarch-cli
```

### With uv (recommended)

```bash
uv tool install monarch-cli
```

### With pipx

```bash
pipx install monarch-cli
```

### Install a tested local checkout

After `uv sync --frozen --all-extras` and `make verify`, run
`./scripts/install-local.sh` (or add `--reinstall` to replace an existing tool).
This uses the checkout's Python and exports constraints from `uv.lock`, so the
installed tool retains the tested runtime and API dependency versions. It does
not log in or access Keychain. Re-run verification after changing the lockfile.

### Verify installation

AXI support is implemented and verified, with a documented API limitation:
unavailable totals remain explicitly unknown. TOON 4.4 is the default; explicit
JSON/CSV schemas remain available. See the [AXI compliance matrix](docs/axi-compliance.md).

The CLI now defaults to TOON. Use `--json` for the original complete JSON schema,
`--fields id,name` for a chosen subset, and `--full` for all fields and untruncated
text. These shared presentation flags work before or after subcommands. Parser
and API errors are structured on stdout; progress and debug diagnostics use stderr.

Use `monarch accounts show ACCOUNT_ID` to inspect native account settings after
an update. Recovery hints retain transaction account/date filters and budget
months. Default receipt rows summarize merchants and linked transactions; tag
rows retain available transaction counts. Explicit NDJSON supports `--fields`.
Transaction and cashflow page limits must be positive; offsets cannot be negative.

```bash
monarch --version
```

## MCP Server (Developers)

This repo includes an MCP server wrapper for the full `monarch` CLI surface.

```bash
uv sync --extra mcp
monarch mcp status
monarch mcp start
```

See `mcp/README.md` for tool details.

### Codex (MCP) setup

No local checkout (uses the public fork):

```bash
codex mcp add monarch -- uvx --from "git+https://github.com/tw4dl/monarch-cli.git" --with mcp monarch mcp start
```

## Quick Start

### 1. Authenticate

```bash
# Login without prompts. Use a UTF-8 file containing your password.
monarch auth login --email EMAIL --password-file PASSWORD_FILE --storage file
# If Monarch requires MFA, repeat with --mfa-code CODE.

# Check authentication status
monarch auth status
```

### 2. List your accounts

```bash
# Human-readable format
monarch accounts list

# JSON format for scripting
monarch accounts list --json
```

### 3. View transactions

```bash
# Recent transactions
monarch transactions list

# This month's transactions
monarch transactions list --preset this-month

# Search for specific transactions
monarch transactions list --search "coffee" --limit 20
```

### 4. Check your budget

```bash
# Current budget status
monarch budgets list

# As JSON for processing
monarch budgets list --json
```

## Command Reference

### Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--version` | `-v` | Show version and exit |
| `--verbose` | `-V` | Show operational progress messages |
| `--debug` | | Show stack traces on errors |
| `--json` | | Output in JSON format |
| `--quiet` | `-q` | Output only IDs, one per line |
| `--no-color` | | Disable colored output |
| `--non-interactive` | | Fail instead of prompting for input |
| `--help` | | Show help and exit |

### Agent Capabilities

Agents can inspect the CLI contract in one deterministic JSON call:

```bash
monarch capabilities --json
```

The manifest includes commands, flags, arguments, JSON support, documented exit
codes, environment variables, and config/session file locations.

Every public command supports `--help`. Each reference lists required inputs,
available flags, explicit defaults (including `false` and `none`), and two or
three examples. Replace sample IDs and file paths with your own values. Examples
use previews where the command supports them. Input errors use exit code 2 and
structured stdout with a repair command; parser repairs retain supplied target IDs.
Interrupted public commands use code 1 and an inspection hint. Progress stays on
stderr, and the error does not suggest replaying an uncertain write.

Deleting an already-absent account, transaction, category, holding, or saved report
returns success with `status: unchanged` after a validated read. Confirmation
guards still apply. Category deletes skip missing IDs and submit each existing
ID once. Delete writes are not automatically retried. A rejected or incomplete
response fails instead of claiming success; bulk category failures also fail.
Normal successful delete JSON envelopes remain unchanged.

Tag set/remove/clear also acknowledge matching state without writing. Removing
tags preserves other tags. Tag writes run once and require a confirmed response.
Raw `api` calls validate the named operation before authentication. Queries may
retry; mutations never automatically retry. Subscriptions are not supported.

Transaction updates also return `status: unchanged` when a read confirms that
every requested field already matches. Missing fields do not prove a match.
Before writing, the CLI requires valid current data for the exact transaction.
The response must confirm every requested value; rejected or ignored fields fail.
Batch updates count unchanged items as successes. Any failed item makes the exit
code 1; structured output retains successes and gives inspection hints for failures.
Budget writes run once and reject missing or rejected payloads. Category and
flexible budget setters require the returned amount to match the requested value.
Holding updates read individual values before and after changes. Matching state
returns `status: unchanged`; aggregate totals cannot verify individual values.
Account updates also skip matching state and require the response to confirm
every requested field. Balance comparisons use the API's displayed balance.
Unknown or ambiguous transaction category names return code 2 and a category-list
hint. Category creation validates the returned ID, name, and group; its default
rollover start is the first day of the current month.
Manual account/tag creation and attachment uploads require confirmed API records.
Tags confirm their name and six-digit RGB color; uploads confirm the filename.
Unconfirmed account creation stops cloning before transaction replay. An
unconfirmed attachment stops any requested note change.
Balance-history uploads require confirmed completion. Input CSV must contain
unique dates, finite amounts, and exactly one `amount` or `balance` column.
Empty or malformed files fail before authentication. Enabled flex rollover
checks the returned period month and starting balance against the request.
Flex rollover independently reads the budget system and active period after writing.
It checks enabled/disabled state, month, and balance. Use `monarch budgets settings`
for read-only inspection. See [native readback evidence](docs/budget-settings-api.md).

Read-only commands retain configured API retries. Public write-capable commands
default to one attempt, including their preparatory API reads. This prevents
automatic replay of an uncertain write. Raw GraphQL queries use their explicit
read retry policy; raw mutations execute once.

Malformed `--fields` syntax fails before dependencies. If a valid selection fails
after a write, the error explains that the operation may have completed and
suggests an inspection command. It never suggests replaying that write. Network
errors omit raw dependency messages; `--debug` puts diagnostics on stderr.
The capabilities manifest marks write-capable commands conservatively, including
the raw `api` escape hatch, which can execute arbitrary mutations.

TOON also presents nested SDK collections with returned and total counts, compact
rows, and clear empty states. The default client preview is 100 rows. `--full`
shows all received rows and fields; server-side pagination still applies.
Nested field selection uses the original paths, such as
`monarch accounts history ACCOUNT_ID --fields snapshots.date,snapshots.signedBalance`.
Cashflow detail applies `--limit` to each complete aggregate list in the TOON
view. Its explicit JSON response remains unchanged.

When a write returns more content than the preview can show, its full-content
hint reads a private local result instead of repeating the write:

```bash
monarch result list
monarch result show RESULT_ID --full
monarch result show RESULT_ID --json
```

The cache holds at most 20 results, up to 10 MiB each, under the Monarch config
directory. Files are private to your user. Results are available for 24 hours;
expired and excess entries are pruned when a new result is saved. No Monarch API
request is needed to read them.

Receipt inbox and security search default to 100 rows. Security search exposes no
verified total-count interface: its TOON output has `total_count: null` and
`total_count_available: false`. This is an accepted API limitation, not an error
or completion blocker. See [security-search evidence](docs/security-search-api.md).

### auth

Authentication management commands.

```bash
monarch auth login --email EMAIL --password-file PASSWORD_FILE --storage keyring
monarch auth login --email EMAIL --password-file PASSWORD_FILE --storage file
monarch auth login --email EMAIL --password-file PASSWORD_FILE --storage file --mfa-code CODE

monarch auth status              # Check authentication status
monarch auth logout              # Log out and clear credentials
monarch auth ping                # Test API connectivity
monarch auth doctor              # Diagnose authentication setup
monarch auth setup               # Show setup instructions
```

Login never prompts. `MONARCH_EMAIL`, `MONARCH_PASSWORD`, and `MONARCH_MFA_CODE`
can supply login values. A password file takes priority over `MONARCH_PASSWORD`.
Only the session token is saved. Missing values fail with exit code 2.

Running `monarch` alone reads live account and review-queue counts. Without a
stored session, it returns an explicit authentication state and a login command.

### Agent session hooks

On invocation, Monarch registers native user hooks for Codex and Claude Code.
It preserves other hooks and settings. Repeated runs repair the absolute
executable path without duplicating hooks. `CODEX_HOME` and `CLAUDE_CONFIG_DIR`
select the respective agent configuration directories.

Session context appears only in directories where Monarch has been run, and their
subdirectories. Home and filesystem roots are excluded. A session-start hook
reads account and review counts. Claude session-end hooks and Codex turn-end hooks
save local transcript metadata and a working-tree file snapshot. Metadata
stays in `<MONARCH_CONFIG_DIR>/hook-history.json`; conversation text, tool arguments,
passwords, tokens, and financial records are not copied. The next session receives
only small summary counts. Transcript tool counts cover at most the last 256 KiB
and are marked as partial when applicable.
Counts include Codex function/custom calls and Claude tool-use blocks; output
records do not count as calls. See [native verification](docs/native-hook-verification.md).

Current Codex requires review of newly registered hooks through `/hooks` or
Settings > Hooks before they execute. Monarch preserves this native trust check.
It enables the current `features.hooks` flag; `codex_hooks` is a deprecated alias.
See the [Codex hook reference](https://learn.chatgpt.com/docs/hooks) and
[Claude Code hook reference](https://code.claude.com/docs/en/hooks).

Set `MONARCH_HOOKS_DISABLED=1` to disable registration. Remove Monarch's registered
entries in the agent hook UI to disable existing hooks. Hook errors produce a
short diagnostic and never block the host session. Native hooks use their host's
wire contract: session-start context is TOON, while Codex Stop emits empty JSON.
Explicit `monarch mcp start` likewise retains the negotiated MCP protocol;
`monarch mcp status` uses the normal structured CLI output.

### accounts

```bash
monarch accounts list            # List all linked accounts
monarch accounts list --json     # JSON format
monarch accounts list --format table  # Table format
monarch accounts list --raw      # Raw API response

monarch accounts refresh         # Refresh all account data
monarch accounts refresh -a ACC123 --wait  # Refresh and wait for sync
monarch accounts refresh-status -a ACC123  # Check refresh completion
monarch accounts history ACC123            # Balance history over time
monarch accounts holdings ACC123           # Holdings for one investment account
monarch accounts recent-balances --start 2024-01-01
monarch accounts snapshots --start 2024-01-01 --timeframe month
monarch accounts aggregate-snapshots --start 2024-01-01 --end 2024-12-31
monarch accounts create --name Cash --type cash --subtype cash --balance 100
monarch accounts create-investments --name "Manual Brokerage" --subtype brokerage \
  --holding SECURITY_ID=100 --exclude-from-net-worth --json
monarch accounts update ACC123 --name "Brokerage" --exclude-from-net-worth
monarch accounts clone-filtered ACC123 --name "IBKR Clean" --dry-run --json
monarch accounts clone-filtered ACC123 --name "IBKR Clean" --target-account ACC456 \
  --normalization-csv usd-overrides.csv --max-writes 25 --json
monarch accounts upload-history ACC123 balances.csv
monarch accounts delete ACC123 --yes
```

`accounts clone-filtered` creates or incrementally updates a manual account while
dropping FX-conversion and minor-interest noise. Brokerage clones preserve balance
history, replay trades and material activity as source-ID-keyed balance-neutral USD
rows, repair drift in existing clone rows, and default to exclusion from net worth
so the linked source balance is not counted twice. Repeated runs resync balance
history and only write new or changed rows. Use `--normalization-csv` for source rows
that lack durable USD evidence and `--max-writes` to process large histories in
retry-safe chunks.

### api

Raw GraphQL escape hatch for Monarch endpoints that do not have first-class CLI commands yet.

```bash
monarch api docs
monarch api docs --output monarch-api-docs.md
monarch api GetAccounts --query 'query GetAccounts { accounts { id displayName } }'
monarch api GetTransactions --query-file query.graphql -F limit=100
monarch api GetTransactions --query-file query.graphql --variables-json '{"limit": 100}'
```

### investments

```bash
monarch investments holdings                    # List visible investment holdings
monarch investments holdings --json             # JSON format
monarch investments holdings --format table     # Table format
monarch investments holdings --aggregate        # Combine by ticker/name
monarch investments holdings --account ACC123   # Query a specific investment account
monarch investments holdings --account ACC123 --detailed --raw --json  # FX audit fields
monarch investments securities LPKFF --json      # Search Monarch's security catalog
monarch investments holding create --account ACC123 --security SEC123 --quantity 100
monarch investments holding update HOLD123 --account ACC123 --quantity 125 --cost-basis 5000
monarch investments holding delete HOLD123 --account ACC123 --yes
```

Holding mutations re-query the exact destination account before reporting success.
`accounts create-investments` creates a holdings-tracked manual account. A unique
same-name account returns `unchanged` only after its subtype, manual tracking,
net-worth settings, and individual holdings match the request. Ambiguous names or
different/unverified state still fail and provide an inspection command. Monarch owns security
market prices: the API accepts security ID, quantity, cost basis, and security type,
but not a custom current price. Treat missing or stale catalog prices as blockers;
do not copy a native-currency value into a USD account or alter share quantity to
force a desired market value.

### transactions

```bash
# List with filters
monarch transactions list
monarch transactions list --limit 50 --offset 0
monarch transactions list --preset this-month
monarch transactions list --start 2024-01-01 --end 2024-01-31
monarch transactions list --account ACC123
monarch transactions list --search "grocery"
monarch transactions list --needs-review
monarch transactions list --has-attachments
monarch transactions list --missing-attachments
monarch transactions list --hidden-from-reports
monarch transactions list --tag TAG123 --category CAT456

# Update a transaction
monarch transactions update TXN123 --amount 25.50
monarch transactions update TXN123 --description "Coffee Shop"
monarch transactions update TXN123 --category CAT456
monarch transactions update TXN123 --notes "Business expense"
monarch transactions update TXN123 --date 2024-01-15
monarch transactions update TXN123 --hide-from-reports
monarch transactions update TXN123 --needs-review
monarch transactions update TXN123 --goal GOAL123
monarch transactions update TXN123 --dry-run --amount 30.00  # Preview

# Create, inspect, delete, and de-duplicate
monarch transactions create --date 2024-01-15 --account ACC123 --amount -12.34 --merchant "Coffee" --category CAT456 --json
monarch transactions create --date 2024-01-15 --account ACC123 --amount 1000 --merchant "Payroll" --category CAT_INCOME --tag TAG123 --dedupe-key date,amount,category,notes --json
monarch transactions upsert --date 2024-01-15 --account ACC123 --amount 1000 --merchant "Payroll" --category CAT_INCOME --notes "January payroll" --tag TAG123 --json
monarch transactions show TXN123
monarch transactions delete TXN123 --yes
monarch transactions duplicates --start 2024-01-01 --account ACC123

# Attach a receipt or supporting document
monarch transactions attach TXN123 ./receipt.pdf
monarch transactions attach TXN123 ./receipt.png --notes "Receipt: dinner, $42.18."
monarch transactions attach TXN123 ./receipt.pdf --filename vendor-receipt.pdf

# Tags and splits
monarch transactions tags list
monarch transactions tags create --name Tax --color "#2f855a"
monarch transactions tags set TXN123 --tag TAG123 --tag TAG456
monarch transactions tags remove TXN123 --tag TAG123
monarch transactions splits show TXN123
monarch transactions splits update TXN123 --splits-file splits.json

# Batch update multiple transactions
monarch transactions batch-update TXN1 TXN2 TXN3 --category CAT456
```

Split updates replace all existing splits; `[]` clears them. Each row requires
`amount` and `categoryId` (`category_id` is also accepted). Optional fields are
`merchantName` (`merchant_name`) and `notes`. Amounts must add up to the parent
amount with the same sign. Matching splits succeed without writing. Writes run
once and require confirmed splits and an unchanged parent amount on readback.

`transactions create --json` and `transactions upsert --json` return a normalized
object with top-level `id`, `status` (`created` or `existing`), transaction fields,
`tag_ids`, and `dedupe_key`. The upstream raw create response nests the ID at
`createTransaction.transaction.id`; the CLI normalizes that shape so scripts can
read `.id` directly. `--tag` is repeatable and is applied before the command
returns success. `upsert` defaults to `--dedupe-key date,amount,category,notes`;
`create` can opt into the same duplicate guard with `--dedupe-key`.
Duplicate checks search the requested account and date completely before creating.
Category filtering applies only when `category` is part of the key. Incomplete
or changing search pages fail safely. Creation uses two-decimal-place rounding,
confirms the created ID and observed fields, and requires requested tags to survive
readback before reporting success.

Metadata-only transaction writes (`update` without `--amount`, attachment
`--notes`, and `batch-update`) first read the current amount, include it in the
Monarch update mutation, and re-read it afterward. If the amount cannot be read
or does not round-trip unchanged, the command fails instead of risking an
implicit amount revert.

**Date Presets:**
- `today`, `yesterday`
- `this-week`, `last-week`
- `this-month`, `last-month`
- `last-30-days`, `last-90-days`
- `this-year`, `last-year`, `ytd`
- `all`

### budgets

```bash
monarch budgets list             # Budget status with spent/remaining
monarch budgets list --start 2024-06-01 --end 2024-06-30
monarch budgets list --json      # JSON format
monarch budgets list --format table
monarch budgets reset --start 2024-06-01
monarch budgets set --category CAT_DINING --amount 800 --start 2024-06-01 --future
monarch budgets set --group GROUP_FOOD --amount 2500
monarch budgets flexible --amount 1200 --future
monarch budgets flex-rollover --start-month 2024-01-01 --starting-balance 0
```

### cashflow

```bash
monarch cashflow summary                      # Current period
monarch cashflow summary --preset this-month  # This month
monarch cashflow summary --preset ytd         # Year to date
monarch cashflow summary -s 2024-01-01 -e 2024-12-31  # Date range
monarch cashflow detail --start 2024-01-01 --end 2024-01-31
monarch cashflow transaction-summary
monarch cashflow recurring --start 2024-06-01 --end 2024-06-30
monarch cashflow credit-history
monarch cashflow subscription
monarch cashflow institutions
```

### categories

```bash
monarch categories list          # All transaction categories
monarch categories list --json   # JSON format
monarch categories groups
monarch categories create --group GROUP_FOOD --name "Dining" --icon D --rollover-enabled
monarch categories delete CAT123 --yes
monarch categories delete CAT123 CAT456 --yes
```

## Output Formats

Monarch CLI supports multiple output formats for different use cases:

| Format | Description | Best For |
|--------|-------------|----------|
| `toon` | Token-efficient structured output (default) | Agents |
| `plain` | Human-readable text | Terminal display |
| `json` | Pretty-printed JSON | Scripts, parsing |
| `table` | Rich table format | Terminal display |
| `csv` | Comma-separated values | Spreadsheets |
| `compact` | Minimal JSON | Compact storage |
| `--ndjson` on `transactions list` | Newline-delimited JSON | Stream processing |

```bash
# Explicit format selection
monarch accounts list --format json
monarch accounts list --format table
monarch accounts list --format csv

# Shorthand for JSON
monarch accounts list --json

# Use explicit JSON when piping to a JSON parser
monarch accounts list --json | jq '.[0]'
```

Mutation commands also accept subcommand-local `--json`/`--format` flags, so
scripts can put output flags at the end of the command. JSON mutation responses
use a stable envelope:

```json
{
  "status": "created|updated|deleted|uploaded|attached|completed|failed|dry_run",
  "entity": "account|budget|category|transaction|transaction_tag|transaction_split",
  "id": "primary-id-when-singular",
  "ids": ["ids-for-batch-or-bulk-commands"],
  "result": {}
}
```

## Configuration

Monarch CLI uses a **layered configuration system** (similar to Git, kubectl, Docker):

```
Config File → Environment Variables → CLI Flags
(lowest precedence)                  (highest precedence)
```

Each layer overrides the previous, giving you flexible control over defaults and per-command behavior.

### Config File

Create `~/.config/monarch-cli/config.toml` to set persistent defaults:

```toml
# Output format: toon, plain, json, table, csv, compact
format = "toon"

# Enable colored output (respects NO_COLOR env var)
color = true

# Show operational progress messages
verbose = false

# API request timeout in seconds
timeout = 30

# Number of retry attempts for transient failures
max_retries = 3
```

### Environment Variables

Environment variables override config file values:

| Variable | Description | Default |
|----------|-------------|---------|
| `MONARCH_TOKEN` | Session token for authentication | - |
| `MONARCH_EMAIL` | Email for `auth login` | - |
| `MONARCH_PASSWORD` | Password for `auth login` when no password file is supplied | - |
| `MONARCH_MFA_CODE` | MFA code for `auth login` | - |
| `MONARCH_HOOKS_DISABLED` | Disable native hook registration (`1`, `true`, `yes`) | `false` |
| `MONARCH_CONFIG_DIR` | Directory for config files | `~/.config/monarch-cli` |
| `MONARCH_SESSION_PATH` | Path to session file | `<config_dir>/session.json` |
| `MONARCH_FORMAT` | Output format (`toon`, `plain`, `json`, `table`, `csv`, `compact`) | `toon` |
| `MONARCH_VERBOSE` | Enable verbose output (`1`, `true`, `yes`) | `false` |
| `MONARCH_DEBUG` | Enable debug mode with stack traces | `false` |
| `MONARCH_QUIET` | Output only IDs, one per line | `false` |
| `MONARCH_TIMEOUT` | API timeout in seconds | `30` |
| `MONARCH_MAX_RETRIES` | Max API retry attempts | `3` |
| `MONARCH_NON_INTERACTIVE` | Fail instead of prompting (`1`, `true`, `yes`) | `false` |
| `MONARCH_NO_COLOR` | Disable colored output | `false` |
| `NO_COLOR` | Standard color disable ([no-color.org](https://no-color.org)) | - |
| `CI` | Enables non-interactive prompt failures when truthy | - |

### CLI Flags

CLI flags override both config file and environment variables:

```bash
# Override format for this command
monarch accounts list --json

# Override timeout for slow connections  
monarch transactions list --timeout 60

# Disable color for this command
monarch accounts list --no-color

# Enable verbose output
monarch accounts list --verbose

# Fail fast instead of prompting
monarch --non-interactive auth login
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Usage error or missing input |

### Authentication Priority

Session credentials are resolved in this order:
1. `MONARCH_TOKEN` environment variable
2. System keyring (if available)
3. Session file (`~/.config/monarch-cli/session.json`)

## Scripting & Automation

Monarch CLI defaults to compact TOON. Request JSON explicitly for existing scripts
and parsers; this preserves the original complete JSON schemas:

```bash
# JSON for scripts
ACCOUNTS=$(monarch accounts list --json | jq '.')

# Explicit JSON mode
monarch transactions list --json --preset this-month

# Quiet mode for IDs only
monarch --quiet accounts list
# Output:
# ACC123456
# ACC789012
```

### Example: Python Integration

```python
import subprocess
import json

def get_transactions(preset="this-month"):
    result = subprocess.run(
        ["monarch", "transactions", "list", "--preset", preset, "--json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

def categorize_transaction(transaction_id, category_id):
    subprocess.run([
        "monarch", "transactions", "update",
        transaction_id, "--category", category_id
    ])

# Get this month's transactions for analysis
transactions = get_transactions("this-month")
print(f"Found {len(transactions)} transactions")
```

### Stable Schema Fields

These output fields are guaranteed stable across versions:

**Accounts:** `id`, `name`, `balance`, `type`, `is_active`, `institution`, `last_synced`

**Transactions:** `id`, `date`, `amount`, `description`, `category`, `account_id`, `is_pending`, `notes`

## Shell Completions

Enable tab completion for commands, options, and arguments:

### Bash

```bash
monarch --install-completion bash
source ~/.bashrc
```

### Zsh

```bash
monarch --install-completion zsh
source ~/.zshrc
```

### Fish

```bash
monarch --install-completion fish
source ~/.config/fish/completions/monarch.fish
```

### Verify

```bash
monarch <TAB>
# Shows: accounts  auth  budgets  cashflow  categories  transactions
```

## Troubleshooting

### Authentication Issues

Run the diagnostic command to identify problems:

```bash
monarch auth doctor
```

This checks:
- Session file existence and permissions
- Token validity
- API connectivity
- Keyring availability

### Common Issues

**"Not authenticated" error:**
```bash
# Re-authenticate
monarch auth login

# Or check status first
monarch auth status
```

**Connection timeout:**
```bash
# Increase timeout
MONARCH_TIMEOUT=60 monarch accounts list

# Or check connectivity
monarch auth ping
```

**Keyring not available (headless systems):**
```bash
# Use file storage instead
monarch auth login -s file
```

### Debug Mode

For detailed error information:

```bash
monarch --debug accounts list
```

## Development

### Setup

```bash
git clone https://github.com/tw4dl/monarch-cli.git
cd monarch-cli

# Install with dev dependencies
make setup
# Or manually:
uv sync --all-extras
```

### Testing

```bash
make test          # Run tests
make test-cov      # Tests with coverage
make lint          # Lint and type check
make verify        # All checks (pre-commit)
```

### Pre-commit hooks

Git hooks are managed with [prek](https://github.com/j178/prek):

```bash
uv run prek install  # Install hooks
```

### Releasing

Releases are a two-step process:

1. **Create GitHub Release** (tags, changelog, artifacts):
   ```bash
   make release-dry  # Preview first
   make release      # Create release
   ```

2. **Publish to PyPI** (separate step):
   ```bash
   uv run twine upload dist/*
   ```

See [docs/RELEASING.md](docs/RELEASING.md) for full instructions including TestPyPI setup and troubleshooting.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run `make verify` to ensure all checks pass
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [monarchmoney](https://github.com/hammem/monarchmoney) - The community Python library for Monarch Money API
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting

## Offline balance export validation

Validate legacy `Date,Balance,Account` CSV files without Monarch credentials:

```bash
python scripts/validate_balances_csv.py balances.csv
```

The validator checks required columns and empty fields. It returns 0 for valid
structure, 1 for empty fields, and 2 for missing files or headers. It does not
validate numeric balances or date formats.

See [legacy export migration](docs/legacy-export-migration.md) for the older
browser exporter and local archive.

Active linked-account refresh: `monarch accounts refresh --active-linked --wait`
and `monarch accounts refresh-status --active-linked --json` use the same scope,
excluding manual valuations and inactive accounts. Empty scopes fail safely.

### Receipt commands

```bash
monarch receipts upload TXN123 ./receipt.pdf --dry-run --json
monarch receipts upload TXN123 ./receipt.pdf --notes "Receipt: dinner"
monarch receipts list TXN123 --json
monarch receipts missing --account ACCOUNT_ID --start 2026-11-01 --end 2026-11-15 --limit 100 --offset 0 --json
```

`upload` shares all options and safeguards with `transactions attach`. Notes replace
existing notes after upload; upload and note update are separate API operations.
`list` returns transaction attachment metadata and asset URLs. `missing` returns
one page of transactions without attachments; use `--offset` for subsequent pages.
Missing attachments do not mean a receipt is required.

The attachment commands above do not trigger OCR or automatic matching. Scanned
image and email receipts use a separate inbox:

```bash
monarch receipts inbox --status pending_matches --limit 25 --json
monarch receipts show RECEIPT_ID --json
monarch receipts match RECEIPT_ID TRANSACTION_ID --dry-run --json
monarch receipts match RECEIPT_ID TRANSACTION_ID --json
```

Inbox output includes `total_count` and `next_offset` for pagination. `show` includes
processing status and `orders[].retailTransactions[].id`. Use `--retail-transaction`
when a receipt has multiple payments or refunds. Matching can update notes,
categories, and splits under Monarch's settings. The CLI checks both targets,
refuses conflicting links, makes no automatic retries, and verifies the resulting
link. On an uncertain result, inspect `show` before retrying.

These commands use Monarch's private API. Inbox and detail reads were checked live;
new matching writes were tested with synthetic responses. See [receipt API details
and limits](docs/receipt-api.md) and the [feature review](docs/feature-review.md).

### Saved reports

```bash
monarch report list --json
monarch report show REPORT_ID --json
monarch report create --name "Tagged cash flow" \
  --url 'https://app.monarch.com/reports/cash-flow?tags=253277239843441604' \
  --dry-run --json
monarch report rename REPORT_ID --name "New name" --dry-run --json
monarch report delete REPORT_ID --dry-run --json
monarch report delete REPORT_ID --yes --json
```

Create, rename, and delete saved Monarch report configurations. Remove `--dry-run`
to apply create/rename. Create supports cash-flow, spending, and income URLs, or
`--filters-file`/`--view-file` JSON objects. Unknown URL settings are rejected;
create preview validates offline. Writes have no automatic retries and require
verified readback. Delete requires `--yes` when not previewing.

A unique same-name report returns `unchanged` only when its complete filters and
view match, including native defaults. Extra filters or incomplete readback still
fail and suggest inspection. Renaming an already-named report is also a no-op.

These commands save views; they do not export report data or change transactions.
The observed update operation renames reports; changing an existing view's filters
in place is not exposed. See [saved-report API details](docs/report-api.md) for
supported input, private API evidence, and validation limits.
