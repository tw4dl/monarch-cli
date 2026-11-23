# Security-search total-count limit

This is a documented API limitation. Totals remain explicitly unknown where
Monarch supplies no verified total contract. No exact total is fabricated.

The verified native `SecuritySearch` document selects `securities` with `search`,
`limit`, and `orderByPopularity`. `Web_SearchSecurities` also selects a bounded
securities array. The current [main bundle](https://static.monarch.com/static/js/main.78766257.js)
contains no selected security-count field or security search cursor/offset
contract. This describes the observed client documents, not every possible
undocumented server capability.

The CLI can report returned size, but reaching a requested limit does not prove
the total number of matches. Larger limits likewise do not establish completeness.
Default output therefore retains `total_count: null` and
`total_count_available: false` when no verified total exists. Explicit JSON keeps
its existing native array schema.

A targeted read-only candidate was tested with:

```graphql
query AXI_SecurityCount { securitiesCount }
```

The server returned:

> Something went wrong while processing: None on request_id: None.

That generic rejection supplied no count or usable argument contract. Earlier
normal schema discovery explicitly returned:

> Introspection queries are disabled for non-admin users.

Neither error proves no undocumented count endpoint exists. A supported total or
complete-pagination contract could improve this output in the future. Until then,
explicit unknowns are the accepted behavior. Returned page size is not presented
as an exact total, and the CLI does not fetch an unbounded catalog to manufacture
one. Raw GraphQL callers can select an appropriate backend count when available.

Codex native delivery/capture and the isolated real-Claude lifecycle test are
verified separately in `native-hook-verification.md`. No native trust/runtime
blocker remains for the tested integrations. The interface retains
this limitation explicitly; see `axi-compliance.md`.
