# -*- coding: utf-8 -*-
"""Write lock & role-based write permission.

Rule: subagents may only write to draft; master may promote to core.
Any direct core write without master role is denied (fail-closed).
"""
import threading

ROLES = ("subagent", "master")
WRITABLE_LAYERS = {"subagent": {"draft"}, "master": {"draft", "hot", "core", "archive"}}


class WriteLock:
    """Mutex for promoting a draft into core (single-writer)."""

    def __init__(self, owner="master"):
        self.owner = owner
        self._lock = threading.Lock()
        self._held_by = None

    def acquire(self, who):
        if self._held_by is not None:
            raise PermissionError("write lock already held by %s" % self._held_by)
        with self._lock:
            if self._held_by is not None:
                raise PermissionError("write lock already held by %s" % self._held_by)
            self._held_by = who
        return True

    def release(self):
        self._held_by = None

    @property
    def held_by(self):
        return self._held_by


def assert_core_write(role):
    """Deny unless the role is master (fail-closed)."""
    if role not in ROLES:
        raise PermissionError("unknown role: %s" % role)
    if "core" not in WRITABLE_LAYERS.get(role, set()):
        raise PermissionError("role %s cannot write core" % role)


def can_write(role, layer):
    """Return True if role may write to layer."""
    return layer in WRITABLE_LAYERS.get(role, set())