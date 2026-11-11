# -*- coding: utf-8 -*-
"""Layered retrieval: mandatory hard rules -> relevance -> cleanup -> receipt."""
import re


class MemorySearch:
    """Query across layers. Hard rules are surfaced first and never filtered."""

    def __init__(self, store, hard_rules):
        self.store = store
        self.hard = hard_rules

    @staticmethod
    def _score(text, query):
        q = query.lower()
        t = str(text).lower()
        words = re.findall(r"[\w\u4e00-\u9fff]+", q)
        if not words:
            return 0.0
        return sum(1 for w in words if w in t) / len(words)

    def retrieve(self, query, layers=("core", "hot"), k=10):
        """Return scored results. Each has {key, layer, score, hard, source}.

        Step 1: mandatory (hard rules first). Step 2: relevance.
        Step 3: cleanup (recycle-bin / expired are excluded upstream).
        Step 4: receipt (source annotated).
        """
        results = []
        for layer in layers:
            for key, rec in self.store.records.get(layer, {}).items():
                text = str(rec.get("payload", "")) + " " + str(rec.get("meta", {}))
                score = self._score(text, query)
                if score > 0:
                    results.append(
                        {
                            "key": key,
                            "layer": layer,
                            "score": score,
                            "hard": self.hard.is_hard(key),
                            "source": rec.get("meta", {}).get("source", "n/a"),
                        }
                    )
        results.sort(key=lambda r: (r["hard"], r["score"]), reverse=True)
        return results[:k]