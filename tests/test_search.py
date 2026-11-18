# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from aml.hardrules import HardRules
from aml.search import MemorySearch
from aml.store import MemoryStore


class MemorySearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self.tmp.name, "mem")
        self.store = MemoryStore(self.base)
        self.rules = HardRules({"risk_redline": {"hard": True}})
        self.search = MemorySearch(self.store, self.rules)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_hit(self):
        self.store.put({"layer": "core", "key": "a", "payload": "meeting minutes agents"})
        res = self.search.retrieve("agents")
        self.assertEqual([r["key"] for r in res], ["a"])

    def test_no_hit(self):
        self.store.put({"layer": "core", "key": "a", "payload": "nothing here"})
        self.assertEqual(self.search.retrieve("agents"), [])

    def test_hard_rule_first(self):
        self.store.put({"layer": "core", "key": "risk_redline", "payload": "no leverage trading agents"})
        self.store.put({"layer": "core", "key": "note", "payload": "agents and memory"})
        res = self.search.retrieve("agents")
        self.assertEqual(res[0]["key"], "risk_redline")
        self.assertTrue(res[0]["hard"])

    def test_receipt_source_annotated(self):
        self.store.put({"layer": "core", "key": "a", "payload": "xyz alpha", "meta": {"source": "agentB"}})
        res = self.search.retrieve("alpha")
        self.assertEqual(res[0]["source"], "agentB")

    def test_k_limit(self):
        for i in range(5):
            self.store.put({"layer": "hot", "key": "k%d" % i, "payload": "common topic %d" % i})
        res = self.search.retrieve("common", k=3)
        self.assertEqual(len(res), 3)


if __name__ == "__main__":
    unittest.main()