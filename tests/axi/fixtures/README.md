# Official TOON encoding fixtures

`toon-4.4.jsonl` contains all 160 encoding cases from the nine encode fixture files
in [toon-format/spec](https://github.com/toon-format/spec/tree/009074d934289553a61763d70c50ee5160e60110/tests/fixtures/encode),
pinned to commit `009074d934289553a61763d70c50ee5160e60110`.

Each line retains the original case and adds `source` and `index` to identify its
original fixture file and array index. No cases were omitted or changed. JSONL
must be split at LF, not at every Unicode line separator: several cases contain
literal U+0085 and U+2028 inside strings.

Source specification: TOON 4.4, dated October 8, 2026. The fixtures cover encoding
only. The CLI is an encoder, not a general TOON decoder. Host normalization,
nonfinite numbers, cycles, and surrogate rejection have additional local tests.

Copyright and permission notice: [TOON-LICENSE](TOON-LICENSE).
