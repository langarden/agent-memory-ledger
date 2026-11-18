# -*- coding: utf-8 -*-
"""LangGraph Checkpointer backed by agent-audit-memory (aml).

Drop-in BaseCheckpointSaver that persists LangGraph checkpoints **as aml
payloads**: every checkpoint write goes through aml WAL -> hash chain, so the
graph's state history is auditable and offline-verifiable (chain.verify()).

This is the companion demo for the "Give LangGraph an auditable memory" tutorial.

Contract boundary (see README Roadmap): aml stores LangGraph checkpoints as
opaque payloads and owns the integrity/audit of those writes. It does NOT
change LangGraph checkpoint semantics; LangGraph-internal bugs / snapshot
overwrites are outside aml's guarantees.

Run:
    python examples/langgraph_checkpointer_demo.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple  # noqa: E402
from langgraph.graph import StateGraph  # noqa: E402

from aml import MemoryStore  # noqa: E402


class AmlCheckpointSaver(BaseCheckpointSaver):
    """Persist LangGraph checkpoints into an aml MemoryStore (audit-grade)."""

    def __init__(self, store: MemoryStore, namespace: str = "langgraph"):
        super().__init__()
        self.store = store
        self.namespace = namespace  # aml namespace = per-graph isolation
        self._seq = 0

    def _serialize(self, obj):
        """Serialize a LangGraph object into JSON-friendly form using the
        base saver's own serde (JsonPlus). bytes -> base64 str."""
        import base64

        typ, blob = self.serde.dumps_typed(obj)
        return {"__aml_serde_type__": typ, "__aml_serde_b64__": base64.b64encode(blob).decode("ascii")}

    def _deserialize(self, holder):
        import base64

        typ = holder["__aml_serde_type__"]
        blob = base64.b64decode(holder["__aml_serde_b64__"].encode("ascii"))
        return self.serde.loads_typed((typ, blob))

    def _key(self, thread_id: str, checkpoint_ns: str = "") -> str:
        return f"{thread_id}::{checkpoint_ns}::{self._seq}"

    def put(self, config, checkpoint, metadata, new_versions):
        """Write one checkpoint into aml (WAL + hash chain). Returns new config."""
        thread_id = (config.get("configurable") or {}).get("thread_id", "default")
        ckpt_key = self._key(thread_id)
        payload = {
            "checkpoint": self._serialize(checkpoint),
            "metadata": self._serialize(metadata),
            "new_versions": self._serialize(new_versions),
            "seq": self._seq,
        }
        self.store.put(
            {
                "layer": "core",
                "key": ckpt_key,
                "payload": payload,
                "meta": {"source": "langgraph-checkpointer", "thread_id": thread_id},
                "sanitize": False,  # serialized blobs are opaque, already-non-secret
            }
        )
        self._seq += 1
        return {"configurable": {**config.get("configurable", {}), "checkpoint_id": ckpt_key}}

    def get_tuple(self, config):
        """Return the latest checkpoint for a thread (or None)."""
        thread_id = (config.get("configurable") or {}).get("thread_id", "default")
        # iterate keys for this thread, newest first (seq desc)
        keys = sorted(
            (k for k in self.store.list_layer("core") if k.startswith(thread_id + "::")),
            key=lambda k: int(k.rsplit("::", 1)[-1]),
            reverse=True,
        )
        if not keys:
            return None
        rec = self.store.get("core", keys[0])
        data = rec["payload"]
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_id": keys[0]}},
            checkpoint=self._deserialize(data["checkpoint"]),
            metadata=self._deserialize(data["metadata"]),
            parent_config=None,
            pending_writes=[],
        )

    def list(self, config=None, *, filter=None, before=None, limit=None):
        """Iterator over checkpoints (newest first). Minimal implementation."""
        thread_id = ((config or {}).get("configurable") or {}).get("thread_id", "default")
        keys = sorted(
            (k for k in self.store.list_layer("core") if k.startswith(thread_id + "::")),
            key=lambda k: int(k.rsplit("::", 1)[-1]),
            reverse=True,
        )
        if limit:
            keys = keys[:limit]
        for k in keys:
            rec = self.store.get("core", k)
            d = rec["payload"]
            yield CheckpointTuple(
                config={"configurable": {"thread_id": thread_id, "checkpoint_id": k}},
                checkpoint=self._deserialize(d["checkpoint"]),
                metadata=self._deserialize(d["metadata"]),
                parent_config=None,
                pending_writes=[],
            )

    def put_writes(self, config, writes, task_id, task_path=""):
        """Persist pending writes (task results). aml owns the integrity/audit."""
        thread_id = (config.get("configurable") or {}).get("thread_id", "default")
        key = f"{thread_id}::{task_id}::writes"
        payload = {
            "task_path": task_path,
            "writes": [self._serialize(w) for w in writes],
        }
        self.store.put(
            {
                "layer": "archive",
                "key": key,
                "payload": payload,
                "meta": {"source": "langgraph-writes", "thread_id": thread_id},
                "sanitize": False,
            }
        )

    # async variants delegate to sync (demo scope)
    async def aput(self, config, checkpoint, metadata, new_versions):
        return self.put(config, checkpoint, metadata, new_versions)

    async def aget_tuple(self, config):
        return self.get_tuple(config)


def main():
    print("== LangGraph <-> agent-audit-memory checkpointer demo ==")
    tmp = tempfile.TemporaryDirectory()
    store = MemoryStore(os.path.join(tmp.name, "mem"), namespace="langgraph-demo")
    try:
        saver = AmlCheckpointSaver(store)

        # minimal graph: count -> count+1 (stateful, so checkpoints matter)
        def step(state):
            return {"count": state["count"] + 1}

        g = StateGraph(dict)
        g.add_node("step", step)
        g.set_entry_point("step")
        g.set_finish_point("step")
        app = g.compile(checkpointer=saver)

        # run twice on the same thread -> two checkpoints
        cfg = {"configurable": {"thread_id": "thread-1"}}
        r1 = app.invoke({"count": 0}, config=cfg)
        r2 = app.invoke({"count": r1["count"]}, config=cfg)
        print("run1 ->", r1)  # {'count': 1}
        print("run2 ->", r2)  # {'count': 2}

        # audit: aml recorded every checkpoint with WAL + hash chain
        ok, bad, total = store.chain.verify()
        print("chain verify:", (ok, bad, total))
        print("stored checkpoints:", len([k for k in store.list_layer("core")]))

        # crash-safety: WAL replay works
        n, bad = store.wal.replay(lambda r: None)
        print("WAL replay:", n, "valid,", bad, "bad")

        # resume: latest checkpoint is thread-1 latest (count state preserved)
        resumed = app.invoke({"count": 99}, config=cfg)
        print("resume ->", resumed)  # {'count': 100}
    finally:
        store.close()
        tmp.cleanup()
    print("== demo OK (exclusive lock released) ==")


if __name__ == "__main__":
    main()