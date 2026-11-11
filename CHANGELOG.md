# Changelog

## v0.1.0 (2026-11-11)

- Initial public release candidate.
- Core engine: `wal.py` (write-ahead log + replay), `chain.py` (hash-chained
  trail + offline verify), `store.py` (draft/hot/core/archive layers).
- Guard rails: `recycle.py` (soft delete, 30-day retention, restore),
  `ledger.py` (conflict ledger + human resolution), `lock.py` (role-based
  write permission, fail-closed), `hardrules.py` (permanent rigid rules).
- Retrieval: `search.py` (hard-first layered retrieval with source receipt).
- Security: `security.py` (digest / sanitize / backup / audit events).
- Demo: `examples/demo.py` (seven-scenario walkthrough).
- Tests: 62 unit tests covering all invariants.