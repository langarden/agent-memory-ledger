# -*- coding: utf-8 -*-
"""Layered memory store: draft / hot / core / archive, WAL-protected."""
import json
import os
import time

from .chain import HashChain
from .security import digest, sanitize
from .util import atomic_write, try_exclusive_lock
from .wal import WalLog

LAYERS = ("draft", "hot", "core", "archive")


class MemoryStore:
    """A small layered store. Every put goes through WAL then hash-chain.

    Concurrency contract (expert review, pre-release):
      * v0.2 enforces a **single-process writer** per storage directory via an
        exclusive cross-process file lock (fail-closed). A second process
        attempting to write raises ProcessContentionError instead of silently
        corrupting files.
      * Within one process, methods are thread-safe for reads; writes are
        serialized by the WAL/chain locks.
      * Pass `exclusive=False` only when you explicitly share the directory
        from another trusted process (not recommended before SQLite backend).
    """

    def __init__(self, base_dir, fsync=False, durability=None, exclusive=True, namespace=None):
        self.base_dir = base_dir
        self.namespace = namespace
        os.makedirs(base_dir, exist_ok=True)
        if namespace:
            # Physical isolation per tenant/session namespace (invariant #9).
            base_dir = os.path.join(base_dir, "namespaces", namespace)
            os.makedirs(base_dir, exist_ok=True)
        self.base_dir = base_dir

        self._exclusive_lock = None
        if exclusive:
            self._exclusive_lock = try_exclusive_lock(
                os.path.join(self.base_dir, "aml.lock"), who="writer"
            )

        self._dirs = {}
        for layer in LAYERS:
            d = os.path.join(base_dir, layer)
            os.makedirs(d, exist_ok=True)
            self._dirs[layer] = d
        os.makedirs(os.path.join(base_dir, "recycle"), exist_ok=True)
        os.makedirs(os.path.join(base_dir, "wal"), exist_ok=True)
        os.makedirs(os.path.join(base_dir, "chain"), exist_ok=True)

        self.wal = WalLog(os.path.join(base_dir, "wal", "wal.log"), fsync=fsync, durability=durability)
        self.chain = HashChain(os.path.join(base_dir, "chain", "chain.jsonl"))
        self.records = {layer: self._load(layer) for layer in LAYERS}
        self.records["recycle"] = self._load("recycle")

    def close(self):
        """Release the exclusive cross-process lock (if held). Safe to call twice."""
        if self._exclusive_lock is not None:
            try:
                self._exclusive_lock.release()
            finally:
                self._exclusive_lock = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _data_path(self, layer):
        return os.path.join(self.base_dir, layer, "data.json")

    def _load(self, layer):
        p = self._data_path(layer)
        if not os.path.exists(p):
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def _persist(self, layer):
        atomic_write(
            self._data_path(layer),
            json.dumps(self.records[layer], ensure_ascii=False, indent=2),
        )

    # -- API -----------------------------------------------------------------
    def put(self, record, source="system"):
        """Write one record. record = {layer,key,payload,meta}. Returns rec_id."""
        layer = record.get("layer")
        key = record.get("key")
        if layer not in LAYERS:
            raise ValueError("bad layer: %s" % layer)
        if not key:
            raise ValueError("empty key")
        payload = record.get("payload")
        payload_hash = digest(payload)
        meta = dict(record.get("meta") or {})
        meta.setdefault("source", source)

        # invariant #7: zero sensitive persistence. By default the payload is
        # sanitized (secrets redacted / hashed) BEFORE storage, so raw secrets
        # never hit disk. Callers that genuinely need raw payloads may pass
        # sanitize=False explicitly, but must then own the data-classification.
        safe_payload = sanitize(payload) if record.get("sanitize", True) else payload
        rec_id = self.wal.append(
            {"op": "put", "layer": layer, "key": key, "payload_hash": payload_hash, "ts": time.time()}
        )
        self.records[layer][key] = {
            "payload": safe_payload,
            "meta": meta,
            "hash": payload_hash,
            "rec_id": rec_id,
            "ts": time.time(),
        }
        self._persist(layer)
        self.chain.append({"op": "put", "layer": layer, "key": key, "payload_hash": payload_hash})
        return rec_id

    def get(self, layer, key, default=None):
        return self.records.get(layer, {}).get(key, default)

    def exists(self, layer, key):
        return key in self.records.get(layer, {})

    def list_layer(self, layer):
        return list(self.records.get(layer, {}).keys())

    def commit_draft(self, key, role="subagent"):
        """Promote a draft record to core. Requires master role (write lock)."""
        from .lock import assert_core_write

        assert_core_write(role)
        rec = self.records["draft"].pop(key)
        self.records["core"][key] = rec
        self._persist("draft")
        self._persist("core")
        self.wal.append({"op": "promote", "key": key, "layer": "core"})
        self.chain.append({"op": "promote", "key": key})
        return rec

    def promote(self, key, to_layer, role="subagent"):
        """Generic layer promotion (draft->hot->core etc). Master only to core."""
        from .lock import assert_core_write

        for layer in ("draft", "hot", "core"):
            if self.exists(layer, key):
                rec = self.records[layer].pop(key)
                if to_layer == "core":
                    assert_core_write(role)
                self.records[to_layer][key] = rec
                self._persist(layer)
                self._persist(to_layer)
                self.wal.append({"op": "promote", "key": key, "layer": to_layer})
                self.chain.append({"op": "promote", "key": key, "to": to_layer})
                return rec
        raise KeyError(key)