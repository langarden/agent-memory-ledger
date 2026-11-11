# -*- coding: utf-8 -*-
"""Write-ahead log: every mutation is appended first, replayable after crash."""
import hashlib
import json
import os
import threading
import time

_FIELDS = ("op", "key", "layer", "payload_hash", "ts")


class WalLog:
    """Append-only, integrity-checked write-ahead log (JSONL)."""

    def __init__(self, path, fsync=False):
        self.path = path
        self.fsync = fsync
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    @staticmethod
    def _rec_id(rec):
        body = json.dumps(
            {k: rec[k] for k in _FIELDS if k in rec},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]

    def append(self, entry):
        """Append one entry. Returns the rec_id (short hash)."""
        with self._lock:
            rec = dict(entry)
            rec.setdefault("ts", time.time())
            rec["rec_id"] = self._rec_id(rec)
            line = json.dumps(rec, ensure_ascii=False)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                if self.fsync:
                    f.flush()
                    os.fsync(f.fileno())
            return rec["rec_id"]

    def read_all(self):
        """Return (valid_records, bad_records_count). Bad tail = crash truncation."""
        recs, bad = [], 0
        if not os.path.exists(self.path):
            return recs, bad
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("rec_id") == self._rec_id(rec):
                        recs.append(rec)
                    else:
                        bad += 1
                except Exception:
                    bad += 1
        return recs, bad

    def replay(self, apply_fn):
        """Replay all valid records through apply_fn. Returns (count, bad)."""
        recs, bad = self.read_all()
        for rec in recs:
            apply_fn(rec)
        return len(recs), bad

    def truncate_last(self):
        """Simulate a crash: remove the final line (for tests / recovery drills)."""
        with self._lock:
            lines = open(self.path, encoding="utf-8").read().splitlines()
            if lines:
                lines = lines[:-1]
                with open(self.path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + ("\n" if lines else ""))