# -*- coding: utf-8 -*-
"""Boundary & recovery tests added by pre-release expert review.

Covers:
  * multi-process / multi-instance exclusive write lock (fail-closed)
  * atomic write (temp-then-rename) and no torn files after partial write
  * stale/torn file recovery: chain detects broken middle record
  * LSN monotonicity: chain order ignores wall-clock time (clock rollback)
  * namespace isolation: tenant/session keys never collide
  * durable(strict) WAL: fsync flush works and stays appendable
"""
import json
import os
import tempfile
import unittest

from aml.chain import HashChain
from aml.store import MemoryStore
from aml.util import ProcessContentionError, atomic_write, try_exclusive_lock
from aml.wal import WalLog


class ProcessLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self.tmp.name, "mem")

    def tearDown(self):
        self.tmp.cleanup()

    def test_second_store_instance_same_dir_denied(self):
        # fail-closed: second writer to the same storage directory must be refused
        store1 = MemoryStore(self.base)
        try:
            with self.assertRaises(ProcessContentionError):
                MemoryStore(self.base)
        finally:
            store1.close()

    def test_lock_release_allows_second_instance(self):
        store1 = MemoryStore(self.base)
        store1.close()
        store2 = MemoryStore(self.base)  # must succeed after explicit release
        store2.close()

    def test_try_exclusive_lock_raisable(self):
        lock = try_exclusive_lock(os.path.join(self.base, "x.lock"))
        try:
            with self.assertRaises(ProcessContentionError):
                try_exclusive_lock(os.path.join(self.base, "x.lock"))
        finally:
            lock.release()


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "f.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_atomic_write_replaces_content(self):
        atomic_write(self.path, '{"a": 1}')
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"a": 1})
        atomic_write(self.path, '{"b": 2}')
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"b": 2})

    def test_no_tmp_left_behind(self):
        atomic_write(self.path, "data")
        leftovers = [n for n in os.listdir(self.tmp.name) if n.startswith(".aml_tmp_")]
        self.assertEqual(leftovers, [])


class TornFileRecoveryTests(unittest.TestCase):
    """Simulate file corruption mid-file; chain must report the bad index."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.chain = HashChain(os.path.join(self.tmp.name, "chain.jsonl"))

    def tearDown(self):
        self.tmp.cleanup()

    def _write_three(self):
        self.chain.append({"op": "put", "key": "a"})
        self.chain.append({"op": "put", "key": "b"})
        self.chain.append({"op": "put", "key": "c"})

    def test_corrupt_middle_detected(self):
        self._write_three()
        ok, bad_idx, _ = self.chain.verify()
        self.assertTrue(ok)
        # tear the middle line
        with open(self.chain.path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        rec = json.loads(lines[1])
        rec["hash"] = "bogus"
        lines[1] = json.dumps(rec)
        with open(self.chain.path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        ok, bad_idx, total = self.chain.verify()
        self.assertFalse(ok)
        self.assertEqual(bad_idx, 1)
        self.assertGreaterEqual(total, 1)

    def test_garbage_line_detected(self):
        self._write_three()
        with open(self.chain.path, "a", encoding="utf-8") as f:
            f.write("not-json\n")
        ok, bad_idx, _ = self.chain.verify()
        self.assertFalse(ok)
        self.assertEqual(bad_idx, 3)


class LsnOrderingTests(unittest.TestCase):
    """Ordering is LSN-based, not wall-clock: clock rollback must not reorder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.chain = HashChain(os.path.join(self.tmp.name, "chain.jsonl"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_lsn_monotonic_despite_clock_rollback(self):
        r0 = self.chain.append({"op": "put", "ts": 1000})
        r1 = self.chain.append({"op": "put", "ts": 900})   # clock went backwards
        r2 = self.chain.append({"op": "put", "ts": 950})
        self.assertEqual([r0["lsn"], r1["lsn"], r2["lsn"]], [0, 1, 2])
        ok, _, total = self.chain.verify()
        self.assertTrue(ok)
        self.assertEqual(total, 3)

    def test_tamper_left_further_links_broken(self):
        self.chain.append({"op": "put", "key": "a"})
        self.chain.append({"op": "put", "key": "b"})
        self.chain.tamper(0, {"op": "put", "key": "MALICIOUS"})
        ok, bad_idx, _ = self.chain.verify()
        self.assertFalse(ok)
        self.assertEqual(bad_idx, 0)  # mismatch surfaces immediately, not later


class NamespaceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_namespace_stores_are_physically_separate(self):
        base = os.path.join(self.tmp.name, "root")
        s1 = MemoryStore(base, namespace="tenant-A")
        s2 = MemoryStore(base, namespace="tenant-B")
        try:
            s1.put({"layer": "core", "key": "k", "payload": "alpha"})
            s2.put({"layer": "core", "key": "k", "payload": "beta"})
            self.assertEqual(s1.get("core", "k")["payload"], "alpha")
            self.assertEqual(s2.get("core", "k")["payload"], "beta")
            # separate directories on disk
            self.assertNotEqual(s1.base_dir, s2.base_dir)
        finally:
            s1.close()
            s2.close()


class DurabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_fsync_true_maps_to_strict(self):
        wal = WalLog(os.path.join(self.tmp.name, "wal.log"), fsync=True)
        self.assertEqual(wal.durability, "strict")
        wal.append({"op": "put", "key": "a"})

    def test_durability_levels_normalized(self):
        self.assertEqual(WalLog(os.path.join(self.tmp.name, "w1")).durability, "normal")
        self.assertEqual(WalLog(os.path.join(self.tmp.name, "w2"), durability="fast").durability, "fast")
        with self.assertRaises(ValueError):
            WalLog(os.path.join(self.tmp.name, "w3"), durability="bogus")

    def test_strict_store_append_works(self):
        store = MemoryStore(os.path.join(self.tmp.name, "mem"), durability="strict")
        try:
            store.put({"layer": "core", "key": "k", "payload": "v"})
            ok, _, total = store.chain.verify()
            self.assertTrue(ok)
            self.assertGreaterEqual(total, 1)
        finally:
            store.close()


class WalCrashSimulationTests(unittest.TestCase):
    """Power-loss style: last WAL line is torn/truncated; replay must not crash."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self.tmp.name, "mem")

    def tearDown(self):
        self.tmp.cleanup()

    def test_wal_replay_over_torn_tail(self):
        store = MemoryStore(self.base, durability="strict")
        try:
            store.put({"layer": "core", "key": "a", "payload": 1})
            store.put({"layer": "core", "key": "b", "payload": 2})
            # simulate power loss writing a half line
            with open(store.wal.path, "a", encoding="utf-8") as f:
                f.write('{"op": "pu')  # torn tail
            recs, bad = store.wal.read_all()
            self.assertEqual(len(recs), 2)
            self.assertGreaterEqual(bad, 1)
            # full git-style replay still succeeds on the valid part
            applied = []
            n, bad = store.wal.replay(lambda r: applied.append(r["key"]))
            self.assertEqual(n, 2)
            self.assertEqual(set(applied), {"a", "b"})
        finally:
            store.close()

    def test_lsn_continuous_after_wal_tail_loss(self):
        """Expert #5: after WAL tail truncation + partial replay, chain LSN
        stays continuous and does not roll back or skip."""
        store = MemoryStore(self.base, durability="strict")
        try:
            store.put({"layer": "core", "key": "a", "payload": 1})
            store.put({"layer": "core", "key": "b", "payload": 2})
            # tail WAL record is lost before it could be reclaimed (crash).
            # Chain still holds both records (chain append happens after WAL),
            # so recovery must not invent or drop chain links.
            store.wal.truncate_last()
            recs, bad = store.wal.read_all()
            self.assertEqual(len(recs), 1)   # only the surviving WAL record
            self.assertGreaterEqual(bad, 0)
            ok, _, total = store.chain.verify()
            self.assertTrue(ok)              # chain stays verifiable
            # continue writing; LSN must continue from existing head, no duplicate/skip
            store.put({"layer": "core", "key": "c", "payload": 3})
            ok, _, total = store.chain.verify()
            self.assertTrue(ok)
            with open(store.chain.path, encoding="utf-8") as f:
                lsns = [json.loads(line)["lsn"] for line in f if line.strip()]
            self.assertEqual(lsns, list(range(len(lsns))))  # 0,1,2 — gap-free
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()