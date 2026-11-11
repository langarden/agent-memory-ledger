# -*- coding: utf-8 -*-
"""Security helpers: digest, sanitize, backups, audit events."""
import hashlib
import json
import os
import re
import shutil
import time

# Default patterns used by sanitize() to redact likely secrets.
# Label prefixes are non-capturing so the whole match becomes [REDACTED].
DEFAULT_PATTERNS = [
    r"(?:password\s*[:=]\s*)\S+",
    r"(?:passwd\s*[:=]\s*)\S+",
    r"(?:token\s*[:=]\s*)\S+",
    r"(?:api[_-]?key\s*[:=]\s*)\S+",
    r"(?:secret\s*[:=]\s*)\S+",
    r"(?:authorization\s*[:=]\s*)\S+",
    r"[A-Za-z0-9+/]{40,}={0,2}",
]

# Dict keys that force the whole value to be redacted regardless of shape.
SENSITIVE_KEY_TOKENS = (
    "password", "passwd", "token", "secret",
    "api_key", "apikey", "authorization", "auth", "private_key",
)


def digest(obj):
    """Stable sha256 of a JSON-serializable object."""
    ser = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(ser).hexdigest()


def sanitize(obj, patterns=None, sensitive_key_tokens=None):
    """Recursively redact secret-like values. Never store raw secrets.

    - Strings matching secret patterns are replaced with [REDACTED].
    - Dict values under sensitive keys (password/token/secret/api_key/...)
      are redacted even if their shape does not match a pattern.
    """
    patterns = patterns or DEFAULT_PATTERNS
    sensitive_key_tokens = sensitive_key_tokens or SENSITIVE_KEY_TOKENS
    if isinstance(obj, str):
        s = obj
        for p in patterns:
            s = re.sub(p, "[REDACTED]", s, flags=re.I)
        return s
    if isinstance(obj, list):
        return [sanitize(x, patterns, sensitive_key_tokens) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            klow = str(k).lower()
            if any(tok in klow for tok in sensitive_key_tokens):
                out[k] = sanitize(v, patterns, sensitive_key_tokens) if isinstance(v, (dict, list)) else "[REDACTED]"
            else:
                out[k] = sanitize(v, patterns, sensitive_key_tokens)
        return out
    return obj


def hash_only(obj):
    """Return only the digest of an object (never the object itself)."""
    return digest(obj)


def backup_dir(src, backup_root, tag=""):
    """Copy a directory into backup_root with a timestamp. Returns dst path."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    name = os.path.basename(src.rstrip("\\/"))
    dst = os.path.join(backup_root, f"{name}_{tag}_{ts}" if tag else f"{name}_{ts}")
    shutil.copytree(src, dst)
    return dst


class AuditLog:
    """Append-only JSONL audit event log."""

    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def record(self, event):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **event}, ensure_ascii=False) + "\n")

    def read(self):
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out