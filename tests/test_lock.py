# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from aml.lock import WriteLock, assert_core_write, can_write
from aml.store import MemoryStore


class WriteLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self.tmp.name, "mem")
        self.store = MemoryStore(self.base)

    def tearDown(self):
        self.tmp.cleanup()

    def test_can_write_matrix(self):
        self.assertTrue(can_write("subagent", "draft"))
        self.assertFalse(can_write("subagent", "core"))
        self.assertTrue(can_write("master", "core"))
        self.assertTrue(can_write("master", "archive"))

    def test_assert_core_write_denies_subagent(self):
        with self.assertRaises(PermissionError):
            assert_core_write("subagent")

    def test_assert_core_write_allows_master(self):
        assert_core_write("master")  # no raise

    def test_assert_core_write_denies_unknown_role(self):
        with self.assertRaises(PermissionError):
            assert_core_write("ghost")

    def test_lock_mutex(self):
        lock = WriteLock()
        self.assertTrue(lock.acquire("master"))
        with self.assertRaises(PermissionError):
            lock.acquire("other")
        lock.release()
        self.assertTrue(lock.acquire("sub"))
        lock.release()

    def test_commit_draft_denied_for_subagent(self):
        self.store.put({"layer": "draft", "key": "d", "payload": "x"})
        with self.assertRaises(PermissionError):
            self.store.commit_draft("d", role="subagent")
        self.assertFalse(self.store.exists("core", "d"))

    def test_commit_draft_allowed_for_master(self):
        self.store.put({"layer": "draft", "key": "d", "payload": "x"})
        rec = self.store.commit_draft("d", role="master")
        self.assertEqual(rec["payload"], "x")
        self.assertTrue(self.store.exists("core", "d"))

    def test_promote_to_core_denied_for_subagent(self):
        self.store.put({"layer": "hot", "key": "h", "payload": "y"})
        with self.assertRaises(PermissionError):
            self.store.promote("h", "core", role="subagent")


if __name__ == "__main__":
    unittest.main()