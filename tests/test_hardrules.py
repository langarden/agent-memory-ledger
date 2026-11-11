# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from aml.hardrules import HardRules


class HardRulesTests(unittest.TestCase):
    def setUp(self):
        self.rules = HardRules({"risk_redline": {"hard": True}})

    def test_is_hard_default_false_for_unknown(self):
        self.assertTrue(self.rules.is_hard("risk_redline"))
        self.assertFalse(self.rules.is_hard("note/alpha"))

    def test_register(self):
        self.rules.register("compliance_minimum", note="x")
        self.assertTrue(self.rules.is_hard("compliance_minimum"))

    def test_decay_skips_hard(self):
        entries = [{"key": "risk_redline", "score": 1.0}, {"key": "note", "score": 1.0}]
        out = self.rules.decay(entries, factor=0.5)
        by_key = {e["key"]: e["score"] for e in out}
        self.assertEqual(by_key["risk_redline"], 1.0)
        self.assertEqual(by_key["note"], 0.5)

    def test_archive_gate_keeps_hard_low_score(self):
        entries = [{"key": "risk_redline", "score": 0.1}, {"key": "note", "score": 0.9}]
        kept = self.rules.archive_gate(entries, threshold=0.5)
        self.assertEqual(sorted(e["key"] for e in kept), ["note", "risk_redline"])

    def test_archive_gate_drops_low_non_hard(self):
        entries = [{"key": "note", "score": 0.1}]
        kept = self.rules.archive_gate(entries, threshold=0.5)
        self.assertEqual(kept, [])

    def test_filter_out_hard(self):
        entries = [{"key": "risk_redline"}, {"key": "note"}]
        out = self.rules.filter_out_hard(entries)
        self.assertEqual([e["key"] for e in out], ["note"])

    def test_load_from_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rules.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"critical": {"hard": true}}')
            rules = HardRules(path=path)
            self.assertTrue(rules.is_hard("critical"))


if __name__ == "__main__":
    unittest.main()