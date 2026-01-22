READ ~/Projects/agent-scripts/AGENTS.MD BEFORE ANYTHING (skip if missing).

# Repository Guidelines

## Project Objective
Export all Monarch Money account balances into CSV files for downstream analysis and archiving.
Target output directory: `output/`.

## Project Structure & Module Organization
- `src/`: primary source code (modules grouped by domain).
- `tests/`: unit/integration tests mirroring `src/` paths.
- `scripts/`: CLI helpers (data imports/exports, one-off utilities).
- `data/`: local fixtures and sample inputs (avoid committing secrets).
- `output/`: generated CSV exports (timestamped files).
- `docs/`: project notes and design docs.

Keep modules small and focused on one responsibility.

## Data Output Format
Exports follow the sample schema `Date,Balance,Account` and are written per account:
- File naming: `output/Balances_<category>-<account>-<YYYY-MM-DDTHH-MM-SS>.csv`
- `Date`: ISO `YYYY-MM-DD`
- `Balance`: decimal number without currency symbols
- `Account`: Monarch account display name

## Build, Test, and Development Commands
Key commands:
- `python -m venv .venv && source .venv/bin/activate`: set up a local virtualenv.
- `pip install -r requirements.txt`: install dependencies.
- `python -m playwright install`: install browser drivers if needed.
- `PYTHONPATH=src python -m monarch_export.export_balances --channel chromium`: run the balances export using the Chromium channel.
- `PYTHONPATH=src python -m monarch_export.export_balances --channel chromium --skip-existing`: skip accounts that already have exports.
- `PYTHONPATH=src python -m monarch_export.export_balances --cdp-port 9222`: attach to a running Chrome session with remote debugging.
- `PYTHONPATH=src python -m monarch_export.combine_balances`: combine all balance exports into `output/all_balances.csv` and write `output/total_balances.png`.
- `python scripts/validate_balances_csv.py output/Balances_<timestamp>.csv`: validate an export.
- `python scripts/rename_balance_exports.py`: rename generic exports to include account slugs.
- `bun scripts/docs-list.ts`: list docs and enforce front matter before doc changes.

Prefer a task runner (e.g., `make`, `just`) for repeatable workflows.

## Coding Style & Naming Conventions
- Indentation: 4 spaces for Python; no tabs.
- File names: `snake_case.py` for modules, `test_*.py` for tests.
- Keep functions short; prefer pure functions for data transforms.
- Keep files ~500 LOC or less; split when they grow.
- If you add a formatter/linter (e.g., `ruff`, `black`), include the config at repo root and document the command here.

## Testing Guidelines
Use `pytest` when adding tests.
- Test file naming: `test_<module>.py`.
- Use fixtures for shared setup; keep tests deterministic.
- Add regression tests for any bug fixes.

## Authentication & Browser Session
Use the existing browser session to reuse Monarch cookies. The exporter should attach to an already-authenticated session rather than prompting for login.
