from __future__ import annotations

import numpy as np

from mind_shared.index.embeddings import EmbeddingBackend
from mind_shared.store import Store
from mind_shared.types import RankedHit


class DenseIndex:
    def __init__(self, store: Store, backend: EmbeddingBackend) -> None:
        self.store = store
        self.backend = backend

    def encode(self, text: str) -> bytes:
        return self.backend.encode(text).astype(np.float32).tobytes()

    def search(self, workspace_id: str, query: str, k: int = 20) -> list[RankedHit]:
        qvec = self.backend.encode(query)
        rows = self.store.fetchall(
            "SELECT id, embedding FROM chunks WHERE workspace_id = ? AND embedding IS NOT NULL",
            (workspace_id,),
        )
        scored: list[tuple[str, float]] = []
        for row in rows:
            vec = np.frombuffer(row["embedding"], dtype=np.float32)
            if vec.size == 0:
                continue
            denom = float(np.linalg.norm(vec) * np.linalg.norm(qvec))
            score = float(np.dot(vec, qvec) / denom) if denom else 0.0
            scored.append((row["id"], score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            RankedHit(chunk_id=chunk_id, score=score, channel="dense")
            for chunk_id, score in scored[:k]
            if score > 0
        ]
