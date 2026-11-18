# -*- coding: utf-8 -*-
"""agent-memory-ledger (aml): a verifiable memory layer for AI agents.

Invariants (fail-closed):
  1. WAL before commit: every mutation is appended to the write-ahead log
     first and can be replayed after a crash.
  2. Triple pre-check: conflict / sensitive / redundant checks before write.
  3. Deletion is soft: records go to the recycle bin (30 days, restorable).
  4. Hash-chained trail: every entry links to the previous hash; verify()
     detects any tamper offline.
  5. hard rules never decay, archive, or get filtered.
  6. Write lock: subagents may only write to draft; master promotes to core.
  7. Zero sensitive payload persistence: only hashes / sanitized values.
  8. Conflicts are surfaced in a ledger for human resolution, never merged
     silently.
  9. Single-writer enforcement: an exclusive cross-process lock guards each
     storage directory (fail-closed multi-process contention).
 10. Provable erasure: purge writes an erasure certificate (digest only) and
     removes plaintext (GDPR Art.17 spot).

Research prototype / AI-assisted development. MIT licensed.
"""

from .wal import WalLog
from .chain import HashChain
from .store import MemoryStore, LAYERS
from .recycle import RecycleBin, DEFAULT_RETENTION
from .ledger import ConflictLedger
from .lock import WriteLock, assert_core_write
from .hardrules import HardRules
from .search import MemorySearch
from .security import digest, sanitize, backup_dir, AuditLog
from .util import FileLock, ProcessContentionError, atomic_write

__all__ = [
    "WalLog",
    "HashChain",
    "MemoryStore",
    "LAYERS",
    "RecycleBin",
    "DEFAULT_RETENTION",
    "ConflictLedger",
    "WriteLock",
    "assert_core_write",
    "HardRules",
    "MemorySearch",
    "digest",
    "sanitize",
    "backup_dir",
    "AuditLog",
    "FileLock",
    "ProcessContentionError",
    "atomic_write",
]

__version__ = "0.2.0"