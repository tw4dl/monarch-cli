# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Password-file login decodes the documented UTF-8 format on every platform.

- Cached results preserve non-ASCII text on systems with a non-UTF-8 default encoding.

- Captured help stays plain and keeps option names intact when CI forces terminal colors.

- Raw GraphQL queries honor configured retries; mutations keep zero automatic retries.
- Full result caching works when the platform lacks Unix file descriptor permission calls.

### Added

- `budgets settings` reads the native budget system and active rollover period for safe inspection.

- Category and budget list output includes relevant read-only discovery hints while preserving explicit JSON schemas.

- `accounts show ACCOUNT_ID` exposes account settings for inspection and recovery. Receipt rows summarize merchants and matches; tag rows include available transaction counts. NDJSON supports field selection.

- Nested TOON collection counts, compact schemas, explicit empty states, original-path field selection, and bounded array previews. Full write responses can be read through a private, expiring `result list/show` cache without replaying mutations. Receipt inbox and catalog search now default to 100 results; unavailable catalog totals remain explicit.

- Consistent help for all public commands, with explicit defaults and reviewed examples. Missing flags, invalid splits, incomplete updates, and unconfirmed deletes now return structured usage errors (code 2) with specific repair or inspection commands. Interrupted public commands return structured errors (code 1) without replay hints for writes.

- Native Codex and Claude lifecycle registration with absolute path repair, directory-scoped context, bounded local metadata capture, and preservation of existing hooks and native trust controls. MCP status now uses structured output and rejects invalid transports before loading the server.

- Flag-complete, noninteractive authentication; structured auth diagnostics and capabilities; a read-only account/review dashboard on bare invocation. Missing input now uses exit code 2; public exit codes are 0/1/2.

- AXI presentation boundary: default TOON, common field selection/full-content flags, compact collections, explicit empty results, retained transaction totals, filter-preserving pagination hints, and structured stdout errors.

- TOON 4.4 output via `--format toon` and `MONARCH_FORMAT=toon`, with official encoder fixtures and a dedicated `make verify-axi` gate. AXI work is verified with documented explicit unknown totals where the API exposes no count.

- Saved report management: list/show, create from a report URL or JSON configuration, rename, and guarded deletion. Includes previews, validated filters, no automatic write retries, and verified readback.

- Scanned receipt inbox and detail commands with processing status, server-side filters, and pagination.
- Explicit scanned receipt matching with target validation, preview, conflict checks, no automatic retries, and verified link readback.
- Receipt command group: upload with preview, list transaction attachments, and find transactions without attachments.
- Active linked-account refresh scope shared by `accounts refresh` and `accounts refresh-status`, excluding manual and inactive accounts and rejecting empty scopes.
- Local installer that uses the tested checkout Python and locked dependency constraints.
- Offline balance CSV validator migrated from the legacy exporter, with malformed-row regression coverage.
- Optional MCP server, holdings mutations, and filtered account cloning.

### Fixed

- Native lifecycle transcript counts now include Codex `custom_tool_call` events while excluding output records and retaining no arguments. Actual Codex Stop capture is verified.

- Flex rollover independently verifies enabled/disabled state, month, and balance through the native UI's settings query. Missing fields cannot masquerade as disabled state; recovery hints use `budgets settings`.

- Flex rollover independently verifies the requested budget system after the write. Failed or contradictory readback returns a scoped inspection command without retrying the mutation; blank system values fail locally.

- Saved-report creation acknowledges complete matching configurations without writing, including native defaults and unrequested-filter checks. Error envelopes cannot establish absence. Holding mutation recovery hints now expose full individual holding values.

- Initial investment holding quantities reject float overflow and nonzero underflow before authentication, instead of sending infinity or silently substituting zero.

- Investment-account creation acknowledges a unique matching existing account with a verified no-op. It checks subtype, manual holdings tracking, net-worth settings, and individual security quantities; conflicting or ambiguous accounts still fail without writing.

- Investment-account creation validates complete account collections before duplicate checks and readback. Blank names/subtypes fail before authentication.

- Registered session-start hooks emit safe unavailable context and an auth diagnostic command when the dashboard fails, while unregistered scopes remain quiet.

- Receipt search validates strict calendar dates and date order before authentication, with structured usage errors. Attachment lists reject error envelopes and mismatched transaction IDs, with a targeted inspection command.

- Holding creation rejects nonfinite quantities and blank identifiers before authentication. Readback verifies the individual holding quantity, without falling back to aggregate security values.

- Holdings lists reject missing account/portfolio collections instead of reporting a false empty portfolio. Valid empty holdings still succeed.

- Recovery hints retain transaction account/date scope and exact budget months. Invalid page bounds fail before authentication. Empty raw API results have explicit TOON states; missing native detail objects return structured errors.

- Transaction creation requires a confirmed canonical record before follow-ups, verifies tag assignment and final tag state, and rejects contradictory readback. Upsert searches all validated pages before creating, rejects incomplete/unstable search data, and honors category omission from dedupe keys. Local input checks run before authentication; native cent rounding is preserved.

- Balance-history uploads require literal SDK completion and return errors on incomplete or malformed results. CSV validation rejects empty files, ambiguous headers, invalid dates, duplicate dates, extra fields, and nonfinite amounts before authentication. Polling values must be positive.
- Enabled flex rollover requires the returned period month and starting balance to match. Default months resolve once before the request; budget dates require YYYY-MM-DD.

- Manual account creation, tag creation, and attachment upload require canonical SDK payloads with confirmed IDs. Tags also confirm name/color and uploads confirm filename. Failed account creation stops cloning before transaction replay; failed attachment binding stops note changes. Nonfinite account balances and malformed tag input fail before authentication.

- Account setters validate inputs, read exact current state, skip matching values, and require confirmation of every requested field, including displayed balances and false visibility flags.
- Category creation now reads the installed SDK's `createCategory.category` response, verifies ID/name/group, and defaults rollover to the first day of the current month. Invalid inputs fail before authentication. Transaction category resolution uses validated collections, gives usage errors for unknown/ambiguous names, and runs once per request.

- Transaction setters reject malformed current state and require the mutation response to confirm every requested field. Invalid amount/date/blank-name input fails before authentication. SDK-shaped tests cover normal and zero updates.
- Public write-capable commands now default to zero automatic retries, including attachment uploads. Read-only commands retain configured retries; raw GraphQL queries keep their explicit read policy.

- Split updates normalize documented field aliases, validate rows and signed totals, acknowledge matching/empty state, disable write retries, and verify returned splits plus parent-amount readback. Split errors point to a scoped split read.

- Holding updates compare and verify individual values through detailed account reads, skip matching state, reject nonfinite inputs, and avoid write retries. Aggregate quantities cannot confirm an individual update.
- Budget reset accepts an explicit null errors field, while malformed rollover periods fail instead of claiming success.

- Batch transaction updates preserve partial results, return code 1 on any failure, acknowledge unchanged items, and replace dependency errors with safe inspection hints.
- Budget writes run once, reject missing/rejected responses, and confirm returned amounts for category and flexible budgets. Invalid dates, empty target IDs, and nonfinite amounts fail before authentication.

- Transaction updates read current state and acknowledge already-matching fields without writing, including empty notes, cleared goals, review flags, and zero amounts. Missing fields never establish a no-op.

- Explicit zero transaction amounts now reach GraphQL and require a confirmed zero response. Metadata changes preserve existing zero amounts. Single transaction updates no longer automatically retry writes.

- Tag setters now read the SDK's canonical transaction field, preserve unrelated tags on removal, acknowledge matching state without writing, and verify write responses. Raw API calls validate the selected operation before authentication and never automatically retry mutations.

- Validated list sources before deriving counts or empty results. Corrected transaction-delete preflight to use the installed SDK's `getTransaction` field, with a real-SDK query-contract test and read-only live verification.

- Repeated deletes now acknowledge verified absence without writing. Deletes reject malformed reads and unconfirmed results, skip duplicate/missing category targets, and disable automatic write retries. Network errors and post-write field-selection failures now provide safe inspection hints without exposing dependency text or suggesting a write replay.

- Transaction update previews without category resolution no longer require authentication.
- **Transaction amount preservation** - Metadata-only transaction updates now include and verify the current amount so note, attachment-note, category, and batch updates do not revert corrected amounts.

## [0.2.0] - 2026-08-27

### Added

#### Layered Configuration System
- **Config file support** - Create `~/.config/monarch-cli/config.toml` for persistent settings
- **Layered precedence** - Config file → Environment variables → CLI flags (highest priority)
- **Source tracking** - `config.get_source("key")` returns where each setting came from (`default`, `file`, `env`, or `cli`)
- **`--timeout` flag** - Override API request timeout per-command (e.g., `monarch accounts list --timeout 60`)

#### Network Resilience
- **Automatic retry** - API calls now retry on transient network errors with exponential backoff
- **Configurable timeout** - `MONARCH_TIMEOUT` and config file `timeout` setting now functional
- **Configurable retries** - `MONARCH_MAX_RETRIES` and config file `max_retries` setting now functional

#### Transaction Attachments
- **Receipt upload command** - `monarch transactions attach TXN123 ./receipt.pdf` uploads a receipt or supporting document to a transaction.
- **Atomic receipt workflow** - `--notes` can update transaction notes after a successful attachment upload.
- **Upload preview** - `--dry-run` validates the file and reports the planned attachment without authenticating or mutating Monarch.

#### API Coverage
- **Account workflows** - Added account history, holdings, recent balances, snapshots, manual account create/update/delete, balance-history upload, refresh waiting, and refresh status commands.
- **Transaction workflows** - Added create/show/delete/duplicates, full list filters, report/review/goal update flags, tag list/create/set/remove/clear, and split show/update commands.
- **Budget workflows** - Added explicit date ranges, reset, category/group budget updates, flexible budget updates, and flex rollover settings.
- **Category workflows** - Added category groups, create, and guarded single/bulk delete commands.
- **Reports workflows** - Added detailed cashflow, transactions summary, recurring transactions, credit history, subscription details, and linked institutions commands.
- **Idempotent manual transactions** - `transactions create` now supports repeatable `--tag` and optional `--dedupe-key`; `transactions upsert` creates only when the default dedupe key does not match an existing row.

#### Agent Ergonomics
- **Capabilities manifest** - Added `monarch capabilities --json` with deterministic command, flag, argument, exit code, environment variable, and config/session file metadata.
- **Non-interactive mode** - Added global `--non-interactive`, `MONARCH_NON_INTERACTIVE`, and `CI` prompt guards. Commands that would prompt now fail fast with exit code `4`.
- **Exit-code contract** - Documented `0` success, `1` general error, `2` usage error, and `4` input needed in help, docs, and the capabilities manifest.
- **JSON auth errors** - Auth commands with explicit `--json` now emit structured JSON errors on stdout instead of leaving stdout empty.

### Changed

- **Default output format** - Changed from `json` to `plain` for interactive terminal use
  - TTY: Human-friendly output with emoji icons
  - Piped/redirected: Automatic JSON output (backwards compatible)
- **Transaction create output** - `transactions create --json` now normalizes the upstream `createTransaction.transaction.id` response to a top-level `id` and includes normalized readback fields for safer scripts.
- **Mutation output schemas** - Account, budget, category, and transaction write commands now accept subcommand-local `--json`/`--format` flags and return normalized envelopes with `status`, `entity`, top-level `id`/`ids`, and `result`.

### Fixed

- **Install dependencies** - Declared the directly imported `click` package and removed the unsupported `typer[all]` extra so clean `pip`, `pipx`, and `uv tool` installs start successfully.
- **Repository metadata** - Updated project, documentation, issue, changelog, clone, and release links for `tw4dl/monarch-cli`.

- **Color auto-detection** - `NO_COLOR`, `TERM=dumb`, and non-TTY now properly disable color
  - Previously, color settings bypassed auto-detection, causing ANSI codes in piped output
- **Environment variables** - `MONARCH_TIMEOUT`, `MONARCH_MAX_RETRIES` were documented but non-functional; now wired up to actual API calls
- **Manual transaction merchant readback** - Created manual transactions preserve the requested merchant name in normalized output when Monarch returns a blank `plaidName`.
- **State-file diagnostics** - Corrupt config/session JSON or TOML files are copied to `*.corrupt.<timestamp>` with a warning instead of being silently ignored.

## [0.1.0] - 2026-01-18

Initial release of Monarch CLI - a command-line interface for Monarch Money.

### Added

#### Authentication Commands
- `monarch auth login` - Interactive login with email/password and optional MFA support
- `monarch auth status` - Show current authentication status
- `monarch auth logout` - Log out and clear stored credentials
- `monarch auth doctor` - Diagnose authentication setup issues
- `monarch auth ping` - Test API connectivity
- `monarch auth setup` - Show setup instructions for new users

#### Account Commands
- `monarch accounts list` - List all linked financial accounts with balances
- `monarch accounts refresh` - Request account refresh from linked institutions

#### Transaction Commands
- `monarch transactions list` - List transactions with powerful filtering options
  - Filter by date range, account, category, amount, search text
  - Support for date presets (today, yesterday, this-week, this-month, etc.)
- `monarch transactions update` - Update transaction properties (notes, category, tags)
- `monarch transactions batch-update` - Batch update multiple transactions at once

#### Budget Commands
- `monarch budgets list` - List all budgets with progress and remaining amounts

#### Cashflow Commands
- `monarch cashflow summary` - View income/expense summary for a date range

#### Category Commands
- `monarch categories list` - List all transaction categories

#### Output Formats
- Multiple output formats: plain, json, table, csv, ndjson, compact
- Auto-detection: JSON when piped, human-friendly in terminal
- `--json` flag to force JSON output
- `--quiet` flag for minimal output (IDs only)
- `--no-color` flag to disable colored output

#### AI Agent Integration
- Stable JSON schema designed for AI agent consumption
- Auto-JSON detection when stdout is piped
- Documented schema contracts for accounts and transactions
- Exit codes and error handling optimized for programmatic use

#### Developer Experience
- Shell completion support for bash, zsh, and fish
- `--verbose` flag for operational progress messages
- `--debug` flag for stack traces on errors
- Comprehensive test suite (91% coverage)
- Type hints throughout codebase

#### Configuration
- `MONARCH_CONFIG_DIR` - Custom config directory location
- `MONARCH_TOKEN` - Direct token authentication (for CI/automation)
- `MONARCH_FORMAT` - Default output format preference
- `MONARCH_TIMEOUT` - Request timeout in seconds
- `MONARCH_VERBOSE` - Enable verbose output
- `NO_COLOR` / `MONARCH_NO_COLOR` - Disable colored output

### Security

- Session tokens stored securely in `~/.config/monarch/session.json`
- No credentials stored after authentication
- Token refresh handled automatically

[Unreleased]: https://github.com/tw4dl/monarch-cli/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tw4dl/monarch-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tw4dl/monarch-cli/releases/tag/v0.1.0
