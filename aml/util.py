# -*- coding: utf-8 -*-
"""Zero-dependency process-level utilities: atomic writes + cross-process lock.

Why this file exists (expert review, pre-release):
  * Multi-process writers against the same JSON/WAL files corrupt state
    (file tearing, broken hash chain). Thread locks are not enough.
  * Plain writes can leave a torn file after a power loss; atomic
    write-then-rename makes a JSON file either fully old or fully new.

Design:
  * atomic_write: write to a temp file in the same directory, fsync, then
    os.replace() over the target. Readers never observe a half-written file.
  * FileLock: best-effort exclusive lock via msvcrt (Windows) or fcntl
    (POSIX). No third-party dependency. Used by MemoryStore to enforce
    single-process writer semantics per storage directory.
"""
import errno
import os
import tempfile

try:  # Windows
    import msvcrt

    _LOCK_IMPL = "msvcrt"
except ImportError:  # POSIX
    import fcntl

    _LOCK_IMPL = "fcntl"


def atomic_write(path, data, encoding="utf-8"):
    """Atomically replace `path` with `data` (string)."""
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".aml_tmp_", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class FileLock:
    """Exclusive advisory lock keyed to a lock file.

    Usage::

        lock = FileLock("mem/aml.lock")
        with lock:
            ...  # only one process at a time

    Non-blocking by default; multi-process second writer raises OSError.
    """

    def __init__(self, path):
        self.path = path
        self._fd = None

    def acquire(self, blocking=False):
        if self._fd is not None:
            return True
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            if _LOCK_IMPL == "msvcrt":
                # Lock the whole file; non-blocking raises OSError.
                msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
            else:
                flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
                fcntl.flock(self._fd, flags)
            return True
        except OSError:
            os.close(self._fd)
            self._fd = None
            raise

    def release(self):
        if self._fd is not None:
            try:
                if _LOCK_IMPL == "msvcrt":
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None

    def __enter__(self):
        self.acquire(blocking=False)
        return self

    def __exit__(self, *exc):
        self.release()
        return False

    def __del__(self):
        # Best-effort release so OS file locks never leak (Windows deletes
        # temp dirs only after all handles are closed).
        try:
            self.release()
        except Exception:
            pass


class ProcessContentionError(OSError):
    """Another process already holds the exclusive store lock."""


def try_exclusive_lock(path, who="writer"):
    """Acquire an exclusive lock or raise ProcessContentionError (fail-closed).

    Returns a FileLock handle whose release() unlocks.
    """
    lock = FileLock(path)
    try:
        lock.acquire(blocking=False)
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK):
            raise ProcessContentionError(
                "another process holds the exclusive lock; role=%s, lock=%s" % (who, path)
            ) from e
        raise
    return lock