from __future__ import annotations

from collections import defaultdict

from mind_shared.config import RRF_K
from mind_shared.types import RankedHit


def reciprocal_rank_fusion(
    *lists: list[RankedHit],
    k: int = RRF_K,
) -> list[RankedHit]:
    scores: dict[str, float] = defaultdict(float)
    hops: dict[str, int] = {}
    paths: dict[str, tuple[str, ...]] = {}
    for ranked in lists:
        for rank, hit in enumerate(ranked, start=1):
            scores[hit.chunk_id] += 1.0 / (k + rank)
            hops[hit.chunk_id] = min(hops.get(hit.chunk_id, hit.hop), hit.hop)
            if hit.entity_path and len(hit.entity_path) >= len(paths.get(hit.chunk_id, ())):
                paths[hit.chunk_id] = hit.entity_path
    fused = [
        RankedHit(
            chunk_id=chunk_id,
            score=score,
            channel="fused",
            hop=hops.get(chunk_id, 0),
            entity_path=paths.get(chunk_id, ()),
        )
        for chunk_id, score in scores.items()
    ]
    fused.sort(key=lambda hit: hit.score, reverse=True)
    return fused
