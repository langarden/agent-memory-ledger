# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from aml.chain import HashChain


class HashChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "chain.jsonl")
        self.chain = HashChain(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_chain_verifies(self):
        ok, bad, total = self.chain.verify()
        self.assertTrue(ok)
        self.assertIsNone(bad)
        self.assertEqual(total, 0)

    def test_appended_chain_verifies(self):
        self.chain.append({"op": "put", "key": "a"})
        self.chain.append({"op": "put", "key": "b"})
        ok, bad, total = self.chain.verify()
        self.assertTrue(ok)
        self.assertEqual(total, 2)

    def test_tamper_middle_detected(self):
        self.chain.append({"op": "put", "key": "a"})
        self.chain.append({"op": "put", "key": "b"})
        self.chain.append({"op": "put", "key": "c"})
        self.chain.tamper(1, {"op": "put", "key": "EVIL"})
        ok, bad, _ = self.chain.verify()
        self.assertFalse(ok)
        self.assertEqual(bad, 1)

    def test_tamper_last_detected(self):
        self.chain.append({"op": "put", "key": "a"})
        self.chain.tamper(0, {"op": "put", "key": "EVIL"})
        ok, bad, _ = self.chain.verify()
        self.assertFalse(ok)
        self.assertEqual(bad, 0)

    def test_indices_increment(self):
        r0 = self.chain.append({"k": 1})
        r1 = self.chain.append({"k": 2})
        self.assertEqual(r0["index"], 0)
        self.assertEqual(r1["index"], 1)
        self.assertEqual(r1["prev_hash"], r0["hash"])

    def test_prev_hash_links(self):
        r0 = self.chain.append({"k": 1})
        r1 = self.chain.append({"k": 2})
        self.assertEqual(r1["prev_hash"], r0["hash"])
        self.assertNotEqual(r0["hash"], r1["hash"])


if __name__ == "__main__":
    unittest.main()