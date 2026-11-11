# agent-memory-ledger

> **A verifiable memory layer for AI agents** — WAL-first writes, hash-chained
> trail, soft-delete recycle bin, conflict ledger, write locks and permanent
> rigid rules, with a **fail-closed** posture.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Tests](https://img.shields.io/badge/tests-63%20passed-green)
![Deps](https://img.shields.io/badge/runtime%20deps-0-green)
![Status](https://img.shields.io/badge/status-research%20prototype-orange)

[中文版](docs/README.zh-CN.md) · *Research prototype / AI-assisted development.*

---

Most agent memory stores help you **remember**. This one also helps you
**prove** that nothing was recorded wrong, deleted silently, or tampered with —
an **audit-grade memory** for agents that need to be accountable.

## Why another memory library?

| Agent memory stores do… | agent-memory-ledger also does… |
|:--|:--|
| store and retrieve memories | **write-ahead log** — crash replayable, nothing lost |
| remember long conversations | **hash-chained trail** — offline `verify()` catches tampering |
| delete old entries | **soft delete + recycle bin** — 30-day retention, restorable |
| update conflicting values | **conflict ledger** — surfaces conflicts for human resolution, never merges silently |
| let agents write freely | **write locks** — subagents write `draft`, master promotes to `core` |
| decay old knowledge | **hard rules** — permanent rigid rules never decay, archive, or filter |

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
pip install agent-memory-ledger   # once published
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

## Roadmap ideas

- MCP server binding (`memory.read` / `memory.write` tools)
- Remote sync with a verifiable chain (append-only replication)
- TTL tiers + decay policy runtime configuration

## Contributing / Security / License

- [CONTRIBUTING.md](CONTRIBUTING.md) — fail-closed first, no new deps,
  sanitized commits, green tests.
- [SECURITY.md](SECURITY.md) — report privately; reference implementation,
  not a hardened product.
- [LICENSE](LICENSE) — MIT, `agent-memory-ledger maintainers`.