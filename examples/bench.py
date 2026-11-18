# -*- coding: utf-8 -*-
"""Micro-benchmark: writes/sec per durability level (used for docs/performance.md).

Usage:
    python examples/bench.py [n]
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aml import MemoryStore  # noqa: E402


def bench(durability, n=200):
    with tempfile.TemporaryDirectory() as tmp:
        s = MemoryStore(os.path.join(tmp, "mem"), durability=durability)
        start = time.perf_counter()
        for i in range(n):
            s.put({"layer": "hot", "key": "k%d" % i, "payload": "v%d" % i})
        dur = time.perf_counter() - start
        s.close()
        return dur / n * 1000


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    print("writes: %d per level, local SSD/dev machine expected" % n)
    print("level   ms/write    writes/sec")
    for d in ("fast", "normal", "strict"):
        ms = bench(d, n)
        print("%-7s %8.3f %12.0f" % (d, ms, 1000.0 / ms))


if __name__ == "__main__":
    main()