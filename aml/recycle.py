# -*- coding: utf-8 -*-
"""Recycle bin: soft deletion with 30-day retention and restore.

Provable erasure (expert review, GDPR Art.17 spot):
  * purge_expired physically removes the plaintext record and writes an
    **erasure certificate** (erased_at / erased_by / payload_digest) into
    <base_dir>/erasure/certificates.jsonl. Only the digest is retained as
    proof that the record existed; the plaintext payload is gone.
  * The hash chain records a `purge` marker, so an offline auditor can
    confirm the record existed and was erased without seeing its content.
"""
import json
import os
import time

from .util import atomic_write

DEFAULT_RETENTION = 30 * 24 * 3600  # 30 days


class RecycleBin:
    """Deletion is soft: records move to recycle, restorable within retention."""

    def __init__(self, store, retention=DEFAULT_RETENTION, erasure_dir=None):
        self.store = store
        self.retention = retention
        self.erasure_dir = erasure_dir or os.path.join(store.base_dir, "erasure")
        os.makedirs(self.erasure_dir, exist_ok=True)

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

    def purge_expired(self, now=None, erased_by="system"):
        """Physically erase expired entries; returns a list of erasure certificates.

        Each certificate retains only the payload digest (proof of existence),
        never the plaintext. Append-only JSONL under `<base>/erasure/`.
        """
        now = now or time.time()
        certs = []
        for key in list(self.store.records["recycle"].keys()):
            rec = self.store.records["recycle"][key]
            if (now - rec.get("__deleted_at", 0)) >= self.retention:
                cert = {
                    "key": key,
                    "from_layer": rec.get("__from_layer"),
                    "erased_at": now,
                    "erased_by": erased_by,
                    "payload_digest": rec.get("hash"),
                    "retention_seconds": self.retention,
                }
                self.store.records["recycle"].pop(key)
                self.store._persist("recycle")
                self.store.wal.append({"op": "purge", "key": key, "erased_at": now})
                self.store.chain.append(
                    {"op": "purge", "key": key, "payload_digest": cert["payload_digest"]}
                )
                self._write_certificate(cert)
                certs.append(cert)
        return certs

    def _write_certificate(self, cert):
        line = json.dumps(cert, ensure_ascii=False)
        path = os.path.join(self.erasure_dir, "certificates.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()

    def read_certificates(self):
        """Read erasure certificates (audit-side helper)."""
        path = os.path.join(self.erasure_dir, "certificates.jsonl")
        if not os.path.exists(path):
            return []
        out = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out