# -*- coding: utf-8 -*-
"""Conflict ledger: surface conflicting writes for human resolution.

Conflicts are never merged silently. A pending conflict blocks the write
until a human resolves it (resolve()).
"""
import json
import os
import threading
import time


class ConflictLedger:
    """Records conflicting writes as pending; resolve() is the human decision."""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.entries = self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        return {"pending": [], "resolved": []}

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    def detect(self, key, incoming, current, source):
        """Return a conflict id if incoming conflicts with current, else None.

        Same-source updates are treated as intentional (no conflict).
        """
        if current is None:
            return None
        if current.get("payload") == incoming:
            return None
        cur_source = current.get("meta", {}).get("source")
        if cur_source == source:
            return None
        entry = {
            "id": "CFL-%d" % int(time.time() * 1000),
            "key": key,
            "incoming": incoming,
            "current": current,
            "source": source,
            "status": "pending",
            "ts": time.time(),
        }
        with self._lock:
            self.entries["pending"].append(entry)
            self._save()
        return entry["id"]

    def list_pending(self):
        return list(self.entries["pending"])

    def has_pending(self, key=None):
        if key is None:
            return bool(self.entries["pending"])
        return any(e["key"] == key for e in self.entries["pending"])

    def resolve(self, cid, decision, by="human"):
        """Resolve a pending conflict with a human decision (keep/incoming/merge)."""
        with self._lock:
            for i, e in enumerate(self.entries["pending"]):
                if e["id"] == cid:
                    e["status"] = "resolved"
                    e["decision"] = decision
                    e["resolved_by"] = by
                    e["resolved_at"] = time.time()
                    self.entries["resolved"].append(e)
                    del self.entries["pending"][i]
                    self._save()
                    return e
        raise KeyError(cid)

    def list_resolved(self):
        return list(self.entries["resolved"])