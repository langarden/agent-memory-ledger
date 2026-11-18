# -*- coding: utf-8 -*-
import os
import tempfile
import time
import unittest

from aml.recycle import RecycleBin, DEFAULT_RETENTION
from aml.store import MemoryStore


class RecycleBinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self.tmp.name, "mem")
        self.store = MemoryStore(self.base)
        self.bin = RecycleBin(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_default_retention(self):
        self.assertEqual(DEFAULT_RETENTION, 30 * 24 * 3600)

    def test_recycle_moves_record(self):
        self.store.put({"layer": "hot", "key": "k", "payload": "v"})
        self.bin.recycle("hot", "k")
        self.assertFalse(self.store.exists("hot", "k"))
        self.assertIn("k", self.store.records["recycle"])

    def test_restore_returns_to_layer(self):
        self.store.put({"layer": "core", "key": "k", "payload": "v"})
        self.bin.recycle("core", "k")
        self.bin.restore("k")
        self.assertTrue(self.store.exists("core", "k"))
        self.assertNotIn("k", self.store.records["recycle"])

    def test_list_shows_not_expired(self):
        self.store.put({"layer": "hot", "key": "k", "payload": "v"})
        self.bin.recycle("hot", "k")
        items = self.bin.list_recycled()
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0]["expired"])
        self.assertGreater(items[0]["retain_secs_left"], 0)

    def test_purge_expired(self):
        self.store.put({"layer": "hot", "key": "k", "payload": "v"})
        self.bin.recycle("hot", "k")
        future = time.time() + 31 * 24 * 3600
        certs = self.bin.purge_expired(now=future, erased_by="test")
        # new contract: returns erasure certificates, not plain keys
        self.assertEqual([c["key"] for c in certs], ["k"])
        self.assertEqual(certs[0]["erased_by"], "test")
        self.assertEqual(self.bin.list_recycled(now=future), [])
        # certificate persisted, plaintext gone
        self.assertEqual(len(self.bin.read_certificates()), 1)
        cert = self.bin.read_certificates()[0]
        self.assertEqual(cert["key"], "k")
        self.assertEqual(len(cert["payload_digest"]), 64)
        # chain carries a purge marker
        ok, _, total = self.store.chain.verify()
        self.assertTrue(ok)
        self.assertGreaterEqual(total, 2)

    def test_no_purge_before_expiry(self):
        self.store.put({"layer": "hot", "key": "k", "payload": "v"})
        self.bin.recycle("hot", "k")
        certs = self.bin.purge_expired()
        self.assertEqual(certs, [])
        self.assertIn("k", self.store.records["recycle"])

    def test_recycle_writes_wal_and_chain(self):
        self.store.put({"layer": "hot", "key": "k", "payload": "v"})
        self.bin.recycle("hot", "k")
        ok, _, total = self.store.chain.verify()
        self.assertTrue(ok)
        self.assertGreaterEqual(total, 2)


if __name__ == "__main__":
    unittest.main()