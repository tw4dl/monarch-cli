# AXI write-command audit

The current capabilities manifest marks 35 command paths as write-capable.
This inventory distinguishes explicit creation/jobs from desired-state setters;
native delivery is verified separately. Unknown totals are the accepted behavior
for APIs without a verified count contract.
All financial mutation evidence below uses synthetic providers. No live writes.

| Paths | Requested behavior and evidence |
| --- | --- |
| `accounts create` | Explicit new account; confirmed canonical payload. `test_creation_confirmation.py` |
| `accounts create-investments` | Unique matching name/settings/individual holdings acknowledge unchanged; different or ambiguous state fails. `test_investment_account_state.py`, `test_investment_account_preflight.py` |
| `accounts clone-filtered` | Reuses verified target/source identities; rejects ambiguous targets and duplicate source markers. Existing account command tests |
| `accounts delete` | Validated absence succeeds; unconfirmed payload fails. `test_delete_idempotency.py` |
| `accounts refresh` | Explicit sync job with scoped status inspection, bounded waiting; not a toggle. Existing command/service tests |
| `accounts update` | Exact requested state skips writes; confirms changed fields. `test_account_state.py` |
| `accounts upload-history` | Native date-keyed upload; local CSV checks and literal completion required. `test_history_upload.py` |
| `api` | Caller chooses query/mutation; mutation retries disabled. Generic operation semantics cannot be inferred. `test_api_operations.py`, `test_write_retries.py` |
| `auth login`, `auth logout` | Flag-only session acquisition/clearing, no prompts. Environment-token boundary is explicit. `test_auth_dashboard.py`, existing auth tests |
| `budgets set`, `budgets flexible`, `budgets flex-rollover`, `budgets reset` | Native setters accept repeated desired values; finite/date checks, payload confirmation, no retries. `test_budget_writes.py`, `test_budget_recovery.py`. Native payload does not independently prove every rollover setting; see compliance matrix |
| `categories create` | Explicit new category with canonical ID/name/group confirmation. `test_category_creation.py` |
| `categories delete` | Validated absence succeeds. `test_delete_idempotency.py` |
| `investments holding create` | Explicit new holding; exact individual quantity readback. `test_holding_creation.py` |
| `investments holding update` | Exact individual requested state skips writes. `test_holding_state.py` |
| `investments holding delete` | Validated absence succeeds; readback confirms deletion. `test_delete_idempotency.py` |
| `receipts match` | Already-linked desired pair succeeds; conflicting link fails. Existing receipt API tests |
| `receipts upload`, `transactions attach` | Explicit new attachment; canonical binding before optional notes. `test_creation_confirmation.py`, `test_write_retries.py` |
| `report create` | A unique complete matching configuration acknowledges unchanged. Compares all filters, including omitted defaults/read-only filter sets, and every view field. Missing/extra/conflicting state stays guarded; backend error envelopes cannot establish absence. `test_report_creation_state.py` |
| `report rename` | Already-named report succeeds unchanged; verified configuration preservation. Existing report API tests |
| `report delete` | Validated absence succeeds; readback confirms deletion. `test_delete_idempotency.py` |
| `transactions create` | Explicit event creation; optional dedupe key uses complete validated search. `test_transaction_creation.py` |
| `transactions upsert` | Existing dedupe match avoids creation; tags use desired-state setter. `test_transaction_creation.py` |
| `transactions update`, `transactions batch-update` | Existing requested state skips writes; amount preservation and partial failure exit checked. `test_transaction_state.py`, `test_transaction_confirmation.py`, `test_batch_errors.py` |
| `transactions splits update` | Exact order-independent split state skips writes; one mutation and verified readback otherwise. `test_split_state.py` |
| `transactions tags set`, `transactions tags remove`, `transactions tags clear` | Set semantics, preserved unrelated tags, no-op when satisfied. `test_tag_state.py` |
| `transactions tags create` | Explicit new tag; canonical ID/name/color confirmed. `test_creation_confirmation.py` |

Cross-cutting evidence: all public commands are noninteractive; missing required
flags fail before dependencies. Structured stdout errors use exit 1 or usage 2;
success/no-op uses 0. Public write-capable paths have no automatic retries, even
for preparatory reads unless explicitly overridden. Uncertain financial outcomes
suggest inspection rather than replay. Parser, backend, interrupt, selection,
and result-cache failures have dedicated tests in `tests/axi`.

Recovery review: exact transaction/split/receipt/report targets; account detail
for metadata, history for balance uploads, refresh status for sync jobs, full
individual holding inspection for holding mutations, and exact raw budget months.
Creation/clone outcomes use complete lists when a new ID is unknown. None suggest
replaying an uncertain financial write. Parser repairs retain known IDs/filters.
Independent rollover verification is now implemented; see `budget-settings-api.md`.
Native lifecycle verification is complete. Exact security counts remain a
documented API limitation with explicit unknown output.

Initial investment quantities reject float overflow and nonzero underflow before
authentication. Native Codex and isolated Claude lifecycle checks passed separately;
see `native-hook-verification.md`. See `axi-completion-audit.md` for the gate results.
