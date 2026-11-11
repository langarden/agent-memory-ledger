# -*- coding: utf-8 -*-
"""Permanent rigid rules (hard rules): exempt from decay/archive/filtering."""
import json
import os


class HardRules:
    """Keys marked hard are never decayed, archived, or filtered."""

    def __init__(self, rules=None, path=None):
        self.rules = dict(rules or {})
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    self.rules[k] = v

    def is_hard(self, key):
        return self.rules.get(key, {}).get("hard", True) if key in self.rules else False

    def register(self, key, **attrs):
        self.rules[key] = {"hard": True, **attrs}

    def decay(self, entries, factor=0.9):
        """Apply score decay to non-hard entries. Hard entries unchanged."""
        out = []
        for e in entries:
            key = e.get("key") or e.get("name")
            if self.is_hard(key):
                out.append(e)
                continue
            e2 = dict(e)
            e2["score"] = e.get("score", 1.0) * factor
            out.append(e2)
        return out

    def archive_gate(self, entries, threshold=0.5):
        """Keep hard rules always; keep others only above score threshold."""
        kept = []
        for e in entries:
            key = e.get("key") or e.get("name")
            if self.is_hard(key) or e.get("score", 1.0) >= threshold:
                kept.append(e)
        return kept

    def filter_out_hard(self, entries):
        """Return non-hard entries only (hard ones are always retained elsewhere)."""
        return [e for e in entries if not self.is_hard(e.get("key") or e.get("name"))]