# Native budget-settings readback

Verified November 21, 2026. No live budget mutation was performed.

## Supported read

```graphql
query Web_GetFlexibleGroupRolloverSettings {
  budgetSystem
  flexExpenseRolloverPeriod { id startMonth startingBalance }
}
```

The query returned the selected fields through the authenticated CLI. It requires
no schema introspection or guessed field names. `monarch budgets settings` exposes
this read directly; explicit JSON retains the native response shape.

The native UI defines the rollover toggle from whether the period is non-null.
The main bundle imports vendor module 26123; that helper applies logical negation
(module 92402, through the lift helper) to the nil predicate (module 61795).
The nil predicate compares its argument to null, including undefined. The UI's
`rolloverEnabled` is therefore true for a returned period and false for null.
A missing API field is incomplete data, not a disabled setting.

After a rollover write, the CLI independently verifies:

- The returned budget system equals the requested system.
- Enabled rollover has a valid period with the requested month and balance.
- Disabled rollover has an explicitly null period.
- Missing/error/malformed or contradictory readback fails with exit 1 and
  `monarch budgets settings` as the inspection command. No financial write repeats.

Existing successful mutation JSON envelopes remain unchanged. Synthetic tests
cover enabled/disabled, absent/null distinction, wrong month/balance, boolean
balance values, rejected responses, and timeout without replay.

## Primary source evidence

- [Current main bundle](https://static.monarch.com/static/js/main.78766257.js):
  native read document and rollover toggle use.
- [Current vendor bundle](https://static.monarch.com/static/js/5927.d9fe853f.js):
  modules 26123, 35286, 95155, 92402, and 61795 establish the non-nil predicate.
- [Earlier route bundle](https://static.monarch.com/static/js/InAppRoutes.33c2c744.chunk.js):
  the rollover form uses the same period-presence contract and update operation.

Obscura supplied focused main/route extraction. Its vendor extraction omitted
parts of the source; one isolated headless Chrome fallback supplied the complete
vendor response. Browser profiles were fresh, with no personal cookies. Requests
used `OpenAI File Downloader, XaiImageApiFetch/1.0`. Source was inspected as data;
no downloaded module was executed as application code.

This resolves independent rollover-enabled readback. The security catalog's
unavailable total remains explicit under the accepted API limitation.
