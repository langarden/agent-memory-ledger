# -*- coding: utf-8 -*-
"""Recycle bin: soft deletion with 30-day retention and restore."""
import time

DEFAULT_RETENTION = 30 * 24 * 3600  # 30 days


class RecycleBin:
    """Deletion is soft: records move to recycle, restorable within retention."""

    def __init__(self, store, retention=DEFAULT_RETENTION):
        self.store = store
        self.retention = retention

    def recycle(self, layer, key, by="system"):
        """Soft-delete a record from a layer into the recycle bin."""
        rec = self.store.records[layer].pop(key)
        rec["__deleted_at"] = time.time()
        rec["__from_layer"] = layer
        rec["__deleted_by"] = by
        self.store.records["recycle"][key] = rec
        self.store._persist(layer)
        self.store._persist("recycle")
        self.store.wal.append({"op": "recycle", "key": key, "layer": layer})
        self.store.chain.append({"op": "recycle", "key": key})
        return rec

    def restore(self, key):
        """Restore a recycled record back to its original layer (within retention)."""
        rec = self.store.records["recycle"].pop(key)
        layer = rec.pop("__from_layer")
        rec.pop("__deleted_at", None)
        rec.pop("__deleted_by", None)
        self.store.records[layer][key] = rec
        self.store._persist("recycle")
        self.store._persist(layer)
        self.store.wal.append({"op": "restore", "key": key, "layer": layer})
        return rec

    def list_recycled(self, now=None):
        now = now or time.time()
        out = []
        for key, rec in self.store.records["recycle"].items():
            deleted_at = rec.get("__deleted_at", 0)
            age = now - deleted_at
            out.append(
                {
                    "key": key,
                    "from_layer": rec.get("__from_layer"),
                    "deleted_at": deleted_at,
                    "expired": age >= self.retention,
                    "retain_secs_left": max(0, self.retention - age),
                }
            )
        return out

    def purge_expired(self, now=None):
        """Physically remove expired entries. Returns list of purged keys."""
        now = now or time.time()
        purged = []
        for key in list(self.store.records["recycle"].keys()):
            rec = self.store.records["recycle"][key]
            if (now - rec.get("__deleted_at", 0)) >= self.retention:
                self.store.records["recycle"].pop(key)
                self.store._persist("recycle")
                self.store.wal.append({"op": "purge", "key": key})
                purged.append(key)
        return purged