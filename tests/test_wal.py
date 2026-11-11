# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from aml.wal import WalLog


class WalLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "wal.log")
        self.wal = WalLog(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_returns_rec_id(self):
        rid = self.wal.append({"op": "put", "key": "a"})
        self.assertEqual(len(rid), 16)

    def test_read_all_empty(self):
        recs, bad = self.wal.read_all()
        self.assertEqual((recs, bad), ([], 0))

    def test_read_all_valid(self):
        self.wal.append({"op": "put", "key": "a", "layer": "core"})
        self.wal.append({"op": "recycle", "key": "b"})
        recs, bad = self.wal.read_all()
        self.assertEqual(len(recs), 2)
        self.assertEqual(bad, 0)

    def test_tail_truncation_detected(self):
        self.wal.append({"op": "put", "key": "a"})
        self.wal.append({"op": "put", "key": "b"})
        # Simulate a crash in the middle of writing a line: partial JSON tail.
        with open(self.path, "a", encoding="utf-8") as f:
            f.write('{"op": "put", "key": "c", "ts": 1')
        recs, bad = self.wal.read_all()
        self.assertEqual(len(recs), 2)
        self.assertEqual(bad, 1)

    def test_replay_counts_and_applies(self):
        self.wal.append({"op": "put", "key": "a"})
        self.wal.append({"op": "put", "key": "b"})
        applied = []
        n, bad = self.wal.replay(lambda r: applied.append(r["key"]))
        self.assertEqual(n, 2)
        self.assertEqual(bad, 0)
        self.assertEqual(applied, ["a", "b"])

    def test_append_same_entry_yields_different_rec_id(self):
        r1 = self.wal.append({"op": "put", "key": "a"})
        r2 = self.wal.append({"op": "put", "key": "a"})
        self.assertNotEqual(r1, r2)


if __name__ == "__main__":
    unittest.main()