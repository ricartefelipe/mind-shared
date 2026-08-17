from __future__ import annotations

from collections import Counter

import numpy as np

from mind_shared.config import BM25_B, BM25_K1
from mind_shared.store import Store
from mind_shared.textutil import content_tokens
from mind_shared.types import RankedHit


class SparseIndex:
    def __init__(self, store: Store) -> None:
        self.store = store

    def index_chunk(self, chunk_id: str, text: str) -> None:
        counts = Counter(content_tokens(text))
        self.store.execute("DELETE FROM terms WHERE chunk_id = ?", (chunk_id,))
        if counts:
            self.store.executemany(
                "INSERT INTO terms(chunk_id, term, tf) VALUES (?, ?, ?)",
                [(chunk_id, term, tf) for term, tf in counts.items()],
            )

    def search(self, workspace_id: str, query: str, k: int = 20) -> list[RankedHit]:
        q_terms = content_tokens(query)
        if not q_terms:
            return []
        stats = self._corpus_stats(workspace_id)
        if stats["n"] == 0 or stats["avgdl"] == 0:
            return []
        scores: dict[str, float] = {}
        for term in q_terms:
            rows = self.store.fetchall(
                """
                SELECT t.chunk_id, t.tf, length(c.text) AS dl
                FROM terms t
                JOIN chunks c ON c.id = t.chunk_id
                WHERE c.workspace_id = ? AND t.term = ?
                """,
                (workspace_id, term),
            )
            df = len(rows)
            if df == 0:
                continue
            idf = np.log((stats["n"] - df + 0.5) / (df + 0.5) + 1.0)
            for row in rows:
                tf = float(row["tf"])
                dl = float(row["dl"])
                denom = tf + BM25_K1 * (1.0 - BM25_B + BM25_B * dl / stats["avgdl"])
                scores[row["chunk_id"]] = scores.get(row["chunk_id"], 0.0) + float(
                    idf * (tf * (BM25_K1 + 1.0)) / denom
                )
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:k]
        return [
            RankedHit(chunk_id=chunk_id, score=score, channel="sparse")
            for chunk_id, score in ranked
        ]

    def _corpus_stats(self, workspace_id: str) -> dict[str, float]:
        row = self.store.fetchone(
            """
            SELECT COUNT(*) AS n, COALESCE(AVG(length(text)), 0) AS avgdl
            FROM chunks
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        )
        if row is None:
            return {"n": 0.0, "avgdl": 0.0}
        return {"n": float(row["n"]), "avgdl": float(row["avgdl"])}
