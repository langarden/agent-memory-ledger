# Changelog

## v0.2.0 (2026-11-18)

Pre-release expert review remediation (data-consistency + compliance accuracy):

- **Multi-process protection**: exclusive cross-process write lock per storage
  directory (fail-closed; second writer raises `ProcessContentionError`).
  `MemoryStore.close()` / context-manager releases the lock.
- **Durability levels**: `WalLog` accepts `durability=strict|normal|fast`
  (legacy `fsync=True/False` still accepted). `strict` fsyncs every append.
- **Atomic writes**: all JSON files now write temp-then-rename; no torn files.
- **LSN ordering**: hash chain records carry a monotonic `lsn`; chain order and
  verification no longer depend on wall-clock time (clock-rollback safe).
- **Provable erasure (GDPR Art.17 spot)**: `purge_expired` writes an erasure
  certificate (digest only, no plaintext) to `<base>/erasure/certificates.jsonl`
  and appends a `purge` marker to the chain.
- **Namespace isolation**: `MemoryStore(..., namespace=...)` gives physical
  per-tenant/per-session storage separation.
- **Tests**: 79 (was 65). Added boundary/recovery suite: process-lock
  fail-closed, atomic-write, torn/corrupt chain detection, LSN monotonicity,
  namespace isolation, durability normalization, WAL replay over torn tail.
- Docs: compliance wording calibrated (technical enabler, not "fully
  compliant"); capacity & concurrency limits documented.

## v0.1.1 (2026-11-12)

- Bump to v0.1.1 (patch) after DaChao R-01~R-04 remediation: sanitize-by-default
  (memory-ledger), LICENSE.audit_guard, docs/prototype badges.
- Tests: 65 OK.

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