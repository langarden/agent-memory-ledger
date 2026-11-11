# agent-memory-ledger

A **verifiable memory layer** for AI agents: write-ahead logging, hash-chained
audit trail, soft-delete recycle bin, conflict ledger, write locks and
permanent rigid rules — with a **fail-closed** posture.

*Research prototype / AI-assisted development. MIT licensed.*

Most agent memory stores help you *remember*. This store also helps you
**prove** that nothing was recorded wrong, deleted silently, or tampered with
— an audit-grade memory.

## Install

```bash
pip install agent-memory-ledger   # once published
# dev / from source:
pip install -e .
```

Zero runtime dependencies. Python 3.9+.

## 5-line example

```python
from aml import MemoryStore, HardRules, RecycleBin

store = MemoryStore("./mem")                       # WAL + hash chain on disk
store.put({"layer": "core", "key": "redline", "payload": "no leverage"})
print(store.chain.verify())                        # (True, None, 1) offline proof
bin = RecycleBin(store); bin.recycle("core", "redline"); bin.restore("redline")
```

Run the seven-scenario walkthrough:

```bash
python examples/demo.py
```

## Why verifiable?

| Invariant | Guarantee |
|:--|:--|
| 1. WAL before commit | every mutation is logged first; crash replayable, nothing lost |
| 2. Triple pre-check | conflict / sensitive / redundant checks gate every write |
| 3. Deletion is soft | records move to a recycle bin (30 days), restorable |
| 4. Hash-chained trail | `verify()` recomputes the chain; any tamper is detected offline |
| 5. Hard rules | permanent rigid rules never decay, archive, or get filtered |
| 6. Write lock | subagents write only `draft`; master promotes to `core` |
| 7. Zero sensitive persistence | secrets are sanitized / stored as hashes only |
| 8. Conflicts surfaced | pending conflicts require human resolution; never merged silently |

## Design posture

**Fail-closed.** Unknown role → deny. Direct core write by a subagent → deny.
Tampered chain → verify fails loudly. Expired recycle entry → purged only
after retention. This project is a research prototype, not a hardened product;
see `SECURITY.md`.

## Architecture

```
aml/
├── wal.py        append-only write-ahead log + crash recovery
├── chain.py      hash-chained audit trail, offline-verifiable
├── store.py      layered store (draft / hot / core / archive)
├── recycle.py    soft delete + 30-day retention + restore
├── ledger.py     conflict ledger (pending -> human resolution)
├── lock.py       role-based write permission (fail-closed)
├── hardrules.py  permanent rigid rules (exempt from decay/archive)
├── search.py     layered retrieval (hard first + source receipt)
└── security.py   digest / sanitize / backup / audit events
```

## Contributing / Security

- [CONTRIBUTING.md](CONTRIBUTING.md) — fail-closed first, no new deps,
  sanitized commits, green tests.
- [SECURITY.md](SECURITY.md) — report privately; this is a reference
  implementation, not a hardened product.

## License

MIT — see [LICENSE](LICENSE). Maintainers: `agent-memory-ledger maintainers`.