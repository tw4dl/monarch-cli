# AXI verification audit

All ten principles are covered in the [interface matrix](axi-compliance.md).
Unknown totals are an intentional API limitation, not an error: known totals stay
exact, while unavailable totals remain explicitly unknown. No total is invented.

## Validation

- `make verify`: 1,501 passed, two native opt-in tests skipped, 23 live tests deselected.
- `make verify-axi`: 744 passed, two native opt-in tests skipped.
- Both native opt-in host tests passed separately: Codex schema loading and real
  isolated Claude 2.1.330 delivery/scoping/SessionEnd with a local model stub.
- Actual Codex SessionStart delivery and thread-matched native Stop capture were
  observed. The custom-tool counter regression is fixed and covered by tests.
- Installed Python source and all 31 runtime dependencies were compared with the
  tested checkout and lockfile.
- All 91 installed help references, structured TOON/JSON usage errors, bare
  dashboards, auth ping, budget settings, and explicit unknown-count behavior passed.
- Explicit JSON/CSV compatibility is covered by existing and new regressions.

Financial writes use synthetic providers; live API checks are read-only. Native
Claude verification uses synthetic finance data and a loopback model endpoint.
No model-provider account is required for that opt-in test.

## Backend limits

Security search returns a bounded native array without a verified total or full
pagination contract. Output retains `total_count: null` and
`total_count_available: false`. Raw GraphQL callers can select backend counts when
available. See [count evidence](security-search-api.md).

Independent rollover readback is supported through the native settings query:
[API evidence](budget-settings-api.md). Both hosts' lifecycle behavior and privacy
boundaries are documented in [native verification](native-hook-verification.md).
