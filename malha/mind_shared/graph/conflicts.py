from __future__ import annotations

from mind_shared.graph.extract import GraphIndex
from mind_shared.textutil import fold, sentences
from mind_shared.types import Contradiction


def graph_conflicts(graph: GraphIndex, workspace_id: str) -> tuple[Contradiction, ...]:
    snapshot = graph.snapshot(workspace_id)
    entities = {item["id"]: item for item in snapshot["entities"]}
    found: list[Contradiction] = []
    for rel in snapshot["relations"]:
        if rel["predicate"] not in {"revoga", "substitui"}:
            continue
        src = entities.get(rel["src"], {})
        dst = entities.get(rel["dst"], {})
        src_name = str(src.get("name") or rel["src"])
        dst_name = str(dst.get("name") or rel["dst"])
        chunk_id = rel["evidence_chunk_id"]
        counter = _counter_chunk(graph, workspace_id, dst.get("canonical", ""), chunk_id)
        found.append(
            Contradiction(
                left_chunk_id=chunk_id,
                right_chunk_id=counter or chunk_id,
                subject=fold(f"{src_name} {dst_name}")[:80],
                left_claim=_chunk_claim(graph, chunk_id) or f"{src_name} {rel['predicate']} {dst_name}",
                right_claim=_chunk_claim(graph, counter) if counter else dst_name,
                reason=f"relação {rel['predicate']} no grafo",
            )
        )
    return tuple(found)


def _counter_chunk(graph: GraphIndex, workspace_id: str, canonical: str, skip: str) -> str | None:
    if not canonical:
        return None
    rows = graph.store.fetchall(
        """
        SELECT ec.chunk_id
        FROM entity_chunks ec
        JOIN entities e ON e.id = ec.entity_id
        WHERE e.workspace_id = ? AND e.canonical = ? AND ec.chunk_id != ?
        LIMIT 1
        """,
        (workspace_id, canonical, skip),
    )
    if not rows:
        return None
    return str(rows[0]["chunk_id"])


def _chunk_claim(graph: GraphIndex, chunk_id: str | None) -> str:
    if not chunk_id:
        return ""
    row = graph.store.fetchone("SELECT text FROM chunks WHERE id = ?", (chunk_id,))
    if row is None:
        return ""
    parts = sentences(str(row["text"])) or [str(row["text"])]
    return parts[0].strip()[:240]
