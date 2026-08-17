from __future__ import annotations

from uuid import uuid4

from mind_shared.store import Store, utcnow
from mind_shared.types import FeedbackLabel, RankedHit


class FeedbackMemory:
    def __init__(self, store: Store) -> None:
        self.store = store

    def record(
        self,
        workspace_id: str,
        chunk_id: str,
        label: FeedbackLabel,
        query_id: str | None = None,
    ) -> str:
        feedback_id = uuid4().hex
        self.store.execute(
            """
            INSERT INTO feedback(id, workspace_id, query_id, chunk_id, label, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (feedback_id, workspace_id, query_id, chunk_id, label.value, utcnow()),
        )
        self.store.commit()
        return feedback_id

    def priors(self, workspace_id: str) -> dict[str, float]:
        rows = self.store.fetchall(
            """
            SELECT chunk_id,
                   SUM(CASE WHEN label = 'useful' THEN 1 ELSE 0 END) AS useful,
                   SUM(CASE WHEN label = 'wrong' THEN 1 ELSE 0 END) AS wrong
            FROM feedback
            WHERE workspace_id = ?
            GROUP BY chunk_id
            """,
            (workspace_id,),
        )
        return {
            row["chunk_id"]: 0.18 * float(row["useful"]) - 0.22 * float(row["wrong"])
            for row in rows
        }

    def rerank(self, workspace_id: str, hits: list[RankedHit]) -> list[RankedHit]:
        prior = self.priors(workspace_id)
        adjusted = [
            RankedHit(
                chunk_id=hit.chunk_id,
                score=hit.score + prior.get(hit.chunk_id, 0.0),
                channel=hit.channel,
                hop=hit.hop,
                entity_path=hit.entity_path,
            )
            for hit in hits
        ]
        adjusted.sort(key=lambda hit: hit.score, reverse=True)
        return adjusted
