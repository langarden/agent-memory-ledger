# -*- coding: utf-8 -*-
"""Hash-chained audit trail: append-only, offline-verifiable."""
import hashlib
import json
import os
import threading
import time

from .util import atomic_write

GENESIS = "0" * 64


class HashChain:
    """Each record stores (lsn, payload, prev_hash, hash). verify() recomputes.

    Ordering is defined by the monotonically increasing `lsn` sequence, not by
    wall-clock time. System clock changes (including rollback) cannot reorder
    or break the chain because each link includes the previous hash.
    """

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def _last_hash(self):
        last = None
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        last = json.loads(line)
        return last["hash"] if last else GENESIS

    def _count(self):
        if not os.path.exists(self.path):
            return 0
        with open(self.path, encoding="utf-8") as f:
            return sum(1 for _ in f)

    def append(self, payload):
        """Append one item. Returns the stored record dict."""
        with self._lock:
            prev = self._last_hash()
            ser = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            digest = hashlib.sha256((ser + "|" + prev).encode("utf-8")).hexdigest()
            lsn = self._count()
            rec = {
                "lsn": lsn,
                "index": lsn,  # legacy alias, same value
                "ts": time.time(),
                "payload": payload,
                "prev_hash": prev,
                "hash": digest,
            }
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
            return rec

    def verify(self):
        """Return (ok, first_bad_index_or_None, total_records)."""
        prev = GENESIS
        total = 0
        if not os.path.exists(self.path):
            return True, None, 0
        with open(self.path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    return False, i, total
                ser = json.dumps(rec["payload"], sort_keys=True, ensure_ascii=False)
                digest = hashlib.sha256((ser + "|" + prev).encode("utf-8")).hexdigest()
                lsn = rec.get("lsn", rec.get("index"))
                if (
                    rec.get("prev_hash") != prev
                    or rec.get("hash") != digest
                    or lsn != i
                ):
                    return False, i, total
                prev = rec["hash"]
                total = i + 1
        return True, None, total

    def tamper(self, index, new_payload):
        """Rewrite a record's payload WITHOUT updating its hash (for tamper tests)."""
        with self._lock:
            with open(self.path, encoding="utf-8") as f:
                lines = f.read().splitlines()
            rec = json.loads(lines[index])
            rec["payload"] = new_payload  # hash left stale -> verify must fail
            lines[index] = json.dumps(rec, ensure_ascii=False)
            atomic_write(self.path, "\n".join(lines) + "\n")