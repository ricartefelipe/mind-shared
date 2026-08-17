from __future__ import annotations

from mind_shared.config import EVIDENCE_K, GRAPH_HOPS_DEFAULT, RETRIEVE_K
from mind_shared.graph.extract import GraphIndex
from mind_shared.index.dense import DenseIndex
from mind_shared.index.hybrid import reciprocal_rank_fusion
from mind_shared.index.sparse import SparseIndex
from mind_shared.memory.feedback import FeedbackMemory
from mind_shared.store import Store
from mind_shared.types import Evidence, RankedHit


class Retriever:
    def __init__(
        self,
        store: Store,
        sparse: SparseIndex,
        dense: DenseIndex,
        graph: GraphIndex,
        feedback: FeedbackMemory,
    ) -> None:
        self.store = store
        self.sparse = sparse
        self.dense = dense
        self.graph = graph
        self.feedback = feedback

    def search(
        self,
        workspace_id: str,
        question: str,
        hops: int = GRAPH_HOPS_DEFAULT,
        k: int = EVIDENCE_K,
    ) -> list[Evidence]:
        sparse_hits = self.sparse.search(workspace_id, question, k=RETRIEVE_K)
        dense_hits = self.dense.search(workspace_id, question, k=RETRIEVE_K)
        fused = reciprocal_rank_fusion(sparse_hits, dense_hits)
        fused = self.feedback.rerank(workspace_id, fused)
        for hop in range(1, max(hops, 0) + 1):
            seed_ids = [hit.chunk_id for hit in fused[:12]]
            entity_ids = self.graph.entities_for_chunks(seed_ids)
            neighbor_entities = self.graph.neighbors(workspace_id, entity_ids)
            hop_chunk_ids = self.graph.chunks_for_entities(neighbor_entities + entity_ids)
            hop_hits = [
                RankedHit(
                    chunk_id=chunk_id,
                    score=1.0 / (hop + 1),
                    channel="graph",
                    hop=hop,
                    entity_path=tuple(neighbor_entities[:4]),
                )
                for chunk_id in hop_chunk_ids
            ]
            fused = self.feedback.rerank(
                workspace_id, reciprocal_rank_fusion(fused, hop_hits)
            )
        return [self._to_evidence(hit) for hit in fused[:k]]

    def _to_evidence(self, hit: RankedHit) -> Evidence:
        row = self.store.fetchone(
            """
            SELECT c.id, c.document_id, c.text, c.start_char, c.end_char, c.ordinal,
                   d.title, d.source_path
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.id = ?
            """,
            (hit.chunk_id,),
        )
        if row is None:
            raise KeyError(hit.chunk_id)
        return Evidence(
            chunk_id=row["id"],
            document_id=row["document_id"],
            document_title=row["title"],
            source_path=row["source_path"],
            excerpt=row["text"],
            score=hit.score,
            hop=hit.hop,
            entity_path=hit.entity_path,
            start_char=int(row["start_char"]),
            end_char=int(row["end_char"]),
            ordinal=int(row["ordinal"]),
        )
