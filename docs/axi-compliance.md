# AXI interface contract

The CLI implements the ten AXI interface principles below. A documented backend
limitation remains: if Monarch does not supply a verified total, output states
that the total is unknown. Returned page size is never substituted for a total.

| Principle | Implementation and evidence |
| --- | --- |
| 1. Token-efficient output | Default TOON 4.4 at the output boundary; internal data remains JSON-shaped; 160 pinned official encoder fixtures |
| 2. Minimal schemas | Compact default collection rows, usually three or four fields; 100-row defaults/previews; original-path `--fields` |
| 3. Bounded content | 1,000-character previews and bounded arrays; `--full` for complete fetched content; cached mutation responses avoid replaying writes |
| 4. Aggregates | Exact backend totals when available, full-array counts before previews, cheap receipt/tag/institution summaries; explicit unknown totals otherwise |
| 5. Empty states | Contextual successful zero states; missing collections and rejected responses do not masquerade as empty results |
| 6. Errors and mutations | Structured stdout errors, exit codes 0/1/2, flag-complete auth, desired-state no-ops, guarded deletes, no automatic financial-write retries |
| 7. Native lifecycle | Self-installing Codex/Claude hooks, absolute path repair, directory-scoped context and bounded local capture; both native hosts tested |
| 8. Content first | Bare invocation reads account/review counts; missing auth returns an explicit state and login command |
| 9. Next steps | Scoped inspection, field, full-content, and pagination hints; uncertain writes suggest inspection rather than replay |
| 10. Local help | Every public command has flags/defaults and two or three reviewed examples; all 91 help references tested |

## Compatibility and presentation

TOON is the normal default. Explicit JSON, CSV, NDJSON, table, plain, and quiet
modes retain their existing framing. `--fields` deliberately projects the requested
fields, including dotted paths, in supported formats. `--full` does not bypass
backend pagination; page hints retain the current filters and offset.

Long fields include a preview and original character count. If a write response
is truncated, a full-result hint reads a private local cache rather than repeating
the operation. The cache is bounded to 20 files, 10 MiB, and 24 hours. Traversal,
symlink, expiration, cleanup-race, and save-failure cases have regression coverage.

Known backend totals survive presentation. Without a verified count contract,
TOON emits `total_count: null` and `total_count_available: false`. Explicit JSON
retains its prior native schema. See [security-search evidence](security-search-api.md).

The encoder targets the [pinned TOON 4.4 specification](https://github.com/toon-format/spec/blob/009074d934289553a61763d70c50ee5160e60110/SPEC.md).
Its fixtures and license are in `tests/axi/fixtures`; no new runtime dependency is
needed. Explicit help/completion and native wire endpoints keep their respective
reference/protocol formats.

## Native hooks and privacy

Public invocations register user-level Codex and Claude hooks by default. Set
`MONARCH_HOOKS_DISABLED=1` to opt out. Existing unrelated settings are preserved;
repeated invocations silently repair executable paths. Native host trust records
are never edited or bypassed. Current Codex uses `[features].hooks = true`.

Context is limited to registered directories and their descendants. Home and
filesystem roots are excluded. SessionStart emits compact context. Codex Stop and
Claude SessionEnd capture transcript references/shape counts and a working-tree
snapshot, not transcript content, arguments, credentials, or financial records.
Counts cover at most the last 256 KiB and carry an explicit partial-tail marker.
Capture retains the latest record for each of at most 100 directory scopes.

See [native host verification](native-hook-verification.md),
[write-command audit](axi-write-audit.md), and
[budget settings evidence](budget-settings-api.md).

## Verification

```bash
make verify
make verify-axi
```

The full gate runs formatting, Ruff, mypy, and non-live tests. Native host tests
are local opt-ins. Financial mutation tests use synthetic providers. Live smoke
checks are read-only. See the [verification audit](axi-completion-audit.md).
