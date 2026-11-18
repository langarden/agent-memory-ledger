# agent-memory-ledger

> **A verifiable memory layer for AI agents** — WAL-first writes, hash-chained
> trail, soft-delete recycle bin, conflict ledger, write locks and permanent
> rigid rules, with a **fail-closed** posture.

```bash
pip install frt-agent-memory-ledger    # zero deps, Python 3.9+
```

> **PyPI name note**: on PyPI this package is published as
> `frt-agent-memory-ledger` (the plain name `agent-memory-ledger` was taken on
> PyPI by an unrelated project; the `frt-` prefix matches the family brand).
> The repo, import path (`import aml`), CLI and everything else are unchanged.

> **Release policy**: until a first external-user validation window closes, PyPI
> releases are published as **pre-release** (`==0.2.0rc1` etc.), not `latest`.
> Pre-release builds are suitable for prototype validation, **not** for
> processing sensitive data. See `docs/performance.md` and
> `docs/compliance.md` before choosing durability/backends.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Tests](https://img.shields.io/badge/tests-79%20passed-green)
![Deps](https://img.shields.io/badge/runtime%20deps-0-green)
![Status](https://img.shields.io/badge/status-research%20prototype-orange)

<a href="https://gitcode.com/gcw_MKhSyoGN/agent-memory-ledger"><img src="https://img.shields.io/badge/GitCode-gcw_MKhSyoGN%2Fagent-memory-ledger-blue" alt="GitCode"></a>
<a href="https://github.com/langarden/agent-memory-ledger"><img src="https://img.shields.io/badge/GitHub-langarden%2Fagent-memory-ledger-black" alt="GitHub"></a>

[中文版](docs/README.zh-CN.md) · *Research prototype / AI-assisted development.*

---

Most agent memory stores help you **remember**. This one also helps you
**prove** that nothing was recorded wrong, deleted silently, or tampered with —
an **audit-grade memory** for agents that need to be accountable.

## Known limitations (read first)

> ⚠️ v0.2 is a research prototype. Read this before filing an issue.

| # | Limitation | Effect / guidance |
|:--|:--|:--|
| 1 | **Single-process writer** per storage directory | enforced by an exclusive lock; second writer raises `ProcessContentionError` with guidance. Recommended: one process, one directory (or per-process `namespace=`). |
| 2 | **No NFS / network shares** as storage backend | atomic rename is unreliable there; local disk only. |
| 3 | **File-store capacity** | tuned for ≤ ~10k records per JSON file; SQLite backend on roadmap. |
| 4 | **No read-side access control** | `namespace=` is data isolation, NOT a security boundary; add OS/object-store ACLs for multi-tenant production. |
| 5 | **Not a legal forensics tool** | erasure certificates / hash chains are internal integrity proofs, not court-grade evidence (see `docs/compliance.md`). |
| 6 | **`durability="strict"` is slow** | fsync per write; use it for audit scenarios, not high-QPS chat agents. See `docs/performance.md`. |
| 7 | **Chain `verify()` is O(n)** | fine ≤ ~100k entries; segmented/snapshot verifier on roadmap. |

## Why another memory library?

| Agent memory stores do… | agent-memory-ledger also does… |
|:--|:--|
| store and retrieve memories | **write-ahead log** — crash replayable, nothing lost |
| remember long conversations | **hash-chained trail** — offline `verify()` catches tampering |
| delete old entries | **soft delete + recycle bin** — 30-day retention, restorable |
| update conflicting values | **conflict ledger** — surfaces conflicts for human resolution, never merges silently |
| let agents write freely | **write locks** — subagents write `draft`, master promotes to `core` |
| decay old knowledge | **hard rules** — permanent rigid rules never decay, archive, or filter |

### The gap this fills

Reliability failures are not edge cases. Common failure modes across popular
agent-memory stores include:

- **A failed write loses the memory body permanently** and leaves no way to
  retry — exactly what a write-ahead log + crash replay prevents.
- **Concurrent writers tear files / corrupt state** during shutdown or shared
  use — a single append-only WAL with an exclusive writer lock removes this
  class of failure.
- **A single corrupted character silently invalidates a whole batch** —
  silent-corruption failures that a hash-chained, offline-verifiable trail
  surfaces immediately instead of propagating.

These are **reliability and verifiability** problems, not "remember harder"
problems. `agent-memory-ledger` is built so that **every write is logged before
it lands, every record is hash-chained and offline-checkable, nothing is
deleted silently, and no conflict is merged without a human** — the ten
invariants below.

## Product family

Part of the **Verifiable-agent family** — the same fail-closed, audit-trail
design language across four repositories (READMEs link each other):

| Repo | Role |
|:--|:--|
| [agent-call-audit](https://gitcode.com/gcw_MKhSyoGN/agent-call-audit) | audit **engine** for agent tool calls |
| **agent-memory-ledger** | verifiable **memory** layer |
| [agent-audit-gateway](https://gitcode.com/gcw_MKhSyoGN/agent-audit-gateway) | HTTP **gateway** around the engine |
| [agent-route-grid](https://gitcode.com/gcw_MKhSyoGN/agent-route-grid) | audited multi-agent **routing** |

## Install

```bash
pip install frt-agent-memory-ledger  # once published
# dev / from source:
pip install -e .
```

Zero runtime dependencies. Python 3.9+.

## 5-line example

```python
from aml import MemoryStore, RecycleBin

store = MemoryStore("./mem")                       # WAL + hash chain on disk
store.put({"layer": "core", "key": "redline", "payload": "no leverage"})
print(store.chain.verify())                        # (True, None, 1) offline proof
bin = RecycleBin(store); bin.recycle("core", "redline"); bin.restore("redline")
```

## Proof of life

Real output from `python examples/demo.py` (seven scenarios):

```
01 write + verify trail   -> trail verify: (True, None, 2)
02 WAL replay after crash -> replayed: 2 bad: 0 applied_keys: ['risk_redline', ...] 
03 hard rule exemption    -> risk_redline score=1.0 (kept) | note/alpha score=0.5
04 conflict resolution    -> conflict CFL-... pending -> after resolve pending: [] 
05 recycle + restore      -> original layer has key: False -> restored: True
06 write lock fail-closed -> subagent write core: False -> denied (fail-closed)
07 sanitize + audit       -> {'password': '[REDACTED]', 'token': '[REDACTED]'}
```

## Invariants

| # | Invariant | Guarantee |
|:--|:--|:--|
| 1 | WAL before commit | every mutation is logged first; crash replayable |
| 2 | Triple pre-check | conflict / sensitive / redundant checks gate every write |
| 3 | Soft delete | records go to a recycle bin (30 days), restorable |
| 4 | Hash-chained trail | `verify()` recomputes the chain; tamper is detected |
| 5 | Hard rules | permanent rigid rules never decay, archive, or filter |
| 6 | Write lock | subagents write `draft` only; master promotes to `core` |
| 7 | Zero sensitive persistence | secrets are sanitized / stored as hashes only |
| 8 | Conflicts surfaced | pending conflicts require human resolution; never merged silently |
| 9 | Single-writer enforcement | exclusive cross-process lock per storage dir (fail-closed) |
| 10 | Provable erasure | purge writes an erasure certificate (digest only), plaintext removed |

**Durability** (`durability=` on `MemoryStore` / `WalLog`): `strict` fsyncs
every append (power-loss safe, audit-grade), `normal` flushes per append
(default), `fast` skips fsync (testing only).

## Concurrency & capacity limits (current file backend)

- **Single-process writer** per storage directory (enforced by an exclusive
  lock — a second writer raises `ProcessContentionError` instead of corrupting
  files). This is the **recommended** v0.2 posture: one agent process, one
  directory. A shared SQLite backend for multi-process write is on the roadmap.
- JSON file store is tuned for **≤ ~10k records per file**; above that, switch
  to the planned SQLite backend (WAL mode, transactional, indexed).
- Chain `verify()` is an O(n) linear pass — fine for ≤ ~100k entries; a
  segmented/snapshot verifier is on the roadmap for larger sets.

## Compliance note (read before citing regulations)

This library provides the **technical substrate** for audit-grade memory —
WAL, hash-chained trail, soft delete + provable erasure, write locks. It does
**not** by itself make a system "GDPR / EU AI Act compliant": full compliance
also requires retention policies, access control on read, operator
procedures, and organisational processes. See `docs/compliance.md` and
`RETAIN_ERASE_POLICY.md` for the current capability envelope. (Managed by
expert review 2026-11.)

## Architecture

```
aml/
├── wal.py        append-only write-ahead log + crash recovery
├── chain.py      hash-chained audit trail (LSN-ordered), offline-verifiable
├── store.py      layered store (draft / hot / core / archive; namespace-isolated)
├── recycle.py    soft delete + 30-day retention + provable erasure certificates
├── ledger.py     conflict ledger (pending -> human resolution)
├── lock.py       role-based write permission (fail-closed)
├── hardrules.py  permanent rigid rules (exempt from decay/archive)
├── search.py     layered retrieval (hard first + source receipt)
├── security.py   digest / sanitize / backup / audit events
└── util.py       atomic writes + exclusive cross-process file lock
```

## Roadmap ideas

- **v0.3 — audit-grade completeness** (per external expert review 2026-11):
  content-level read access control; provenance chain (which prompt / tool
  call produced a memory); configurable retention tiers + auto-archive; export
  of an independent audit-event stream.
- **Scalability — SQLite backend (architecture constraint)**: when adding the
  SQLite store, **do not re-implement the JSON-file hash-chain at file level**.
  SQLite already provides WAL + transactions + row locks; the hash-chain
  semantic should be pushed down to **row level** rather than stacking a second
  WAL on top. Two nested WAL layers add avoidable complexity and consistency
  risk.
- **Ecosystem — LangGraph/LangChain `Checkpointer` binding (contract
  boundary)**: the compatibility layer stores LangGraph checkpoints **as aml
  payloads** and aml owns the integrity/audit of those writes. It does **not**
  change LangGraph checkpoint semantics; LangGraph-internal bugs / checkpoint
  overwrites are outside aml's guarantees. A **separate demo repository**
  (not the main repo) will host the LangGraph integration demo + compliance
  export scripts, keeping the main repo clean so users can clone-and-run.
- **MCP server** (`memory.read` / `memory.write`); **remote sync** with a
  verifiable append-only chain.

## Contributing / Security / License / AI disclosure

- [CONTRIBUTING.md](CONTRIBUTING.md) — fail-closed first, no new deps,
  sanitized commits, green tests.
- [SECURITY.md](SECURITY.md) — report privately; reference implementation,
  not a hardened product; no third-party security audit yet.
- [docs/compliance.md](docs/compliance.md) — capability envelope vs EU AI Act
  / GDPR; [RETAIN_ERASE_POLICY.md](RETAIN_ERASE_POLICY.md) — retention &
  provable-erasure policy; [docs/AUDIT_LOG_FORMAT.md](docs/AUDIT_LOG_FORMAT.md)
  — log schema for third-party audit tooling.
- [docs/AIGC_DISCLOSURE.md](docs/AIGC_DISCLOSURE.md) — AI-assisted development
  disclosure.
- [LICENSE](LICENSE) — MIT, `agent-memory-ledger maintainers`.