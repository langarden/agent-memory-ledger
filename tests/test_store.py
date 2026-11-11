# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from aml.store import LAYERS, MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self.tmp.name, "mem")
        self.store = MemoryStore(self.base)

    def tearDown(self):
        self.tmp.cleanup()

    def test_layers(self):
        self.assertEqual(LAYERS, ("draft", "hot", "core", "archive"))

    def test_put_get_roundtrip(self):
        self.store.put({"layer": "core", "key": "k1", "payload": "v1", "meta": {"source": "m"}})
        rec = self.store.get("core", "k1")
        self.assertEqual(rec["payload"], "v1")
        self.assertEqual(rec["meta"]["source"], "m")

    def test_bad_layer_rejected(self):
        with self.assertRaises(ValueError):
            self.store.put({"layer": "bogus", "key": "k", "payload": "v"})

    def test_empty_key_rejected(self):
        with self.assertRaises(ValueError):
            self.store.put({"layer": "hot", "key": "", "payload": "v"})

    def test_get_default(self):
        self.assertIsNone(self.store.get("core", "missing"))
        self.assertEqual(self.store.get("core", "missing", default="x"), "x")

    def test_list_layer_and_exists(self):
        self.store.put({"layer": "hot", "key": "a", "payload": 1})
        self.store.put({"layer": "hot", "key": "b", "payload": 2})
        self.assertEqual(sorted(self.store.list_layer("hot")), ["a", "b"])
        self.assertTrue(self.store.exists("hot", "a"))
        self.assertFalse(self.store.exists("core", "a"))

    def test_promote_draft_to_core(self):
        self.store.put({"layer": "draft", "key": "d1", "payload": "x"})
        self.store.commit_draft("d1", role="master")
        self.assertTrue(self.store.exists("core", "d1"))
        self.assertFalse(self.store.exists("draft", "d1"))

    def test_generic_promote(self):
        self.store.put({"layer": "hot", "key": "h1", "payload": "y"})
        self.store.promote("h1", "archive", role="master")
        self.assertTrue(self.store.exists("archive", "h1"))

    def test_trail_recorded_per_write(self):
        self.store.put({"layer": "core", "key": "k1", "payload": "v1"})
        self.store.put({"layer": "core", "key": "k2", "payload": "v2"})
        ok, _, total = self.store.chain.verify()
        self.assertTrue(ok)
        self.assertGreaterEqual(total, 2)


if __name__ == "__main__":
    unittest.main()