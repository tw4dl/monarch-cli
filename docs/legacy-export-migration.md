# Legacy export migration

The earlier `Projects/python/monarch-cli` checkout is a separate export project,
not an older checkout of this CLI. Its `monarch_export` package uses Playwright
to download balances, combines CSV histories, and plots total balances. Its
scripts rename exports and normalize a historical NetWorthAccount.

The useful offline CSV validator now lives in `scripts/validate_balances_csv.py`
and has regression tests, including truncated CSV rows. It needs only Python's
standard library.

The remaining legacy code, tests, requirements, design notes, input data, and
export files are preserved locally in `local-legacy/monarch-export/`. This folder
is excluded through `.git/info/exclude`; it must stay out of commits because it
contains personal financial data. It also contains `history.bundle`,
`uncommitted.patch`, and `git-status.txt` to preserve the older Git state.
The original checkout remains as a backup. This local archive does not ship with
the package or exist in a fresh clone.

To run the archived offline tests from a consolidated checkout:

```bash
PYTHONPATH=local-legacy/monarch-export/src uv run pytest local-legacy/monarch-export/tests -q
```

The old tests stub browser and plotting dependencies when unavailable. Passing
these tests does not prove that the browser exporter still matches Monarch's UI
or that a real plot renders. Use this CLI's authenticated API commands for current
account access. The legacy browser flow and year-specific NetWorthAccount
normalization require review before reuse.
