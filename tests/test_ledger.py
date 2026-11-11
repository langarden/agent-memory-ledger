# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from aml.ledger import ConflictLedger


class ConflictLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "ledger.json")
        self.ledger = ConflictLedger(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def _cur(self, payload, source="master"):
        return {"payload": payload, "meta": {"source": source}}

    def test_no_conflict_when_current_missing(self):
        cid = self.ledger.detect("k", "v", None, source="a")
        self.assertIsNone(cid)

    def test_no_conflict_same_value(self):
        cur = self._cur("v")
        cid = self.ledger.detect("k", "v", cur, source="other")
        self.assertIsNone(cid)

    def test_no_conflict_same_source(self):
        cur = self._cur("v1", source="agentA")
        cid = self.ledger.detect("k", "v2", cur, source="agentA")
        self.assertIsNone(cid)

    def test_conflict_different_source(self):
        cur = self._cur("v1", source="agentA")
        cid = self.ledger.detect("k", "v2", cur, source="agentB")
        self.assertIsNotNone(cid)
        self.assertTrue(self.ledger.has_pending(key="k"))

    def test_resolve_clears_pending(self):
        cur = self._cur("v1", source="agentA")
        cid = self.ledger.detect("k", "v2", cur, source="agentB")
        self.ledger.resolve(cid, decision="keep-current", by="human")
        self.assertEqual(self.ledger.list_pending(), [])
        self.assertEqual(len(self.ledger.list_resolved()), 1)
        self.assertFalse(self.ledger.has_pending())

    def test_resolve_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            self.ledger.resolve("CFL-999", decision="keep")

    def test_persistence_across_reload(self):
        cur = self._cur("v1", source="agentA")
        cid = self.ledger.detect("k", "v2", cur, source="agentB")
        # reload from disk
        ledger2 = ConflictLedger(self.path)
        self.assertTrue(ledger2.has_pending(key="k"))
        ledger2.resolve(cid, decision="keep", by="human")
        ledger3 = ConflictLedger(self.path)
        self.assertFalse(ledger3.has_pending())


if __name__ == "__main__":
    unittest.main()