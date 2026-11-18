# -*- coding: utf-8 -*-
"""Seven-scenario walkthrough for agent-memory-ledger."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aml import (  # noqa: E402
    AuditLog,
    ConflictLedger,
    HardRules,
    MemorySearch,
    MemoryStore,
    RecycleBin,
    sanitize,
)
from aml.lock import can_write  # noqa: E402


def scenario(name, fn):
    print("== %s ==" % name)
    fn()
    print()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "mem")
        store = MemoryStore(base)
        rules = HardRules({"risk_redline": {"hard": True}})
        search = MemorySearch(store, rules)
        audit = AuditLog(os.path.join(tmp, "audit", "events.jsonl"))

        # 1. write + hash-chain verify
        scenario("01 write + verify trail", lambda: (
            store.put({"layer": "core", "key": "risk_redline", "payload": "no leverage", "meta": {"source": "master"}}),
            store.put({"layer": "hot", "key": "note/alpha", "payload": "meeting notes about agents", "meta": {"source": "sub"}}),
            print("trail verify:", store.chain.verify()),
            print("record:", store.get("core", "risk_redline")),
        ))

        # 2. WAL replay (crash recovery)
        def s02():
            applied = []
            n, bad = store.wal.replay(lambda r: applied.append((r["op"], r["key"])))
            print("replayed:", n, "bad:", bad, "applied_keys:", [k for _, k in applied[:3]], "...")
        scenario("02 WAL replay after crash", s02)

        # 3. hard rule survives decay
        def s03():
            entries = [
                {"key": "risk_redline", "score": 1.0},
                {"key": "note/alpha", "score": 1.0},
            ]
            decayed = rules.decay(entries, factor=0.5)
            for e in decayed:
                print(e["key"], "score=", e["score"])
            kept = rules.archive_gate(decayed, threshold=0.6)
            print("kept:", [e["key"] for e in kept])
        scenario("03 hard rule exempt from decay/archive", s03)

        # 4. conflict -> human resolution
        def s04():
            ledger = ConflictLedger(os.path.join(tmp, "ledger.json"))
            cid = ledger.detect("note/alpha", "v1", store.get("hot", "note/alpha"), source="other")
            print("conflict:", cid, "pending:", ledger.list_pending())
            ledger.resolve(cid, decision="keep-current", by="human")
            print("after resolve pending:", ledger.list_pending(), "resolved:", len(ledger.list_resolved()))
        scenario("04 conflict ledger + human resolution", s04)

        # 5. recycle bin restore
        def s05():
            bin = RecycleBin(store)
            bin.recycle("hot", "note/alpha")
            print("recycled:", bin.list_recycled())
            print("original layer has key:", store.exists("hot", "note/alpha"))
            bin.restore("note/alpha")
            print("restored:", store.exists("hot", "note/alpha"))
        scenario("05 soft delete -> recycle -> restore", s05)

        # 6. write lock: subagent cannot write core
        def s06():
            print("subagent write draft:", can_write("subagent", "draft"))
            print("subagent write core:", can_write("subagent", "core"))
            try:
                store.commit_draft("risk_redline", role="subagent")
                print("UNEXPECTED: subagent promoted")
            except PermissionError as e:
                print("denied (fail-closed):", e)
        scenario("06 write lock fail-closed", s06)

        # 7. sanitize secrets
        def s07():
            dirty = {"password": "sup3rs3cret", "token": "abc123token", "desc": "plain text"}
            print("sanitized:", sanitize(dirty))
            audit.record({"event": "demo", "level": "info"})
            print("audit events:", len(audit.read()))
        scenario("07 sanitize + audit trail", s07)

        print("search 'agents' ->", [r["key"] for r in search.retrieve("agents")])

        # release the exclusive process lock before the temp dir is cleaned up
        store.close()


if __name__ == "__main__":
    main()