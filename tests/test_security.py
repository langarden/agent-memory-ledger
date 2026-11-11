# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from aml.security import AuditLog, backup_dir, digest, hash_only, sanitize


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_digest_stable(self):
        self.assertEqual(digest({"a": 1}), digest({"a": 1}))
        self.assertNotEqual(digest({"a": 1}), digest({"a": 2}))

    def test_hash_only_never_returns_secret(self):
        self.assertNotIn("secret-value", hash_only("secret-value"))
        self.assertEqual(len(hash_only("anything")), 64)

    def test_sanitize_password(self):
        out = sanitize({"password": "p@ss", "x": 1})
        self.assertNotIn("p@ss", out["password"])
        self.assertIn("REDACTED", out["password"])

    def test_sanitize_token(self):
        out = sanitize("token=abc123xyz")
        self.assertNotIn("abc123xyz", out)

    def test_sanitize_long_secret_like_string(self):
        long_secret = "A" * 50  # looks like a base64 secret
        out = sanitize(long_secret)
        self.assertEqual(out, "[REDACTED]")

    def test_sanitize_recursive(self):
        out = sanitize({"nested": [{"api_key": "k1234567890"}]})
        self.assertNotIn("k1234567890", str(out))

    def test_backup_dir_copies(self):
        src = os.path.join(self.tmp.name, "data")
        os.makedirs(src)
        with open(os.path.join(src, "f.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        dst_root = os.path.join(self.tmp.name, "backups")
        dst = backup_dir(src, dst_root, tag="pre")
        self.assertTrue(os.path.exists(os.path.join(dst, "f.txt")))

    def test_audit_log_record_read(self):
        path = os.path.join(self.tmp.name, "audit", "events.jsonl")
        log = AuditLog(path)
        log.record({"event": "write", "key": "k"})
        log.record({"event": "read", "key": "k"})
        events = log.read()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event"], "write")


if __name__ == "__main__":
    unittest.main()