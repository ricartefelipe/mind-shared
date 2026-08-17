from __future__ import annotations

import json
from pathlib import Path

from mind_shared.engine import Mesh
from mind_shared.types import QueryResult


def recall_at_k(retrieved_titles: list[str], relevant_titles: list[str], k: int) -> float:
    if not relevant_titles:
        return 1.0
    got = {title.lower() for title in retrieved_titles[:k]}
    need = {title.lower() for title in relevant_titles}
    return len(got.intersection(need)) / len(need)


def faithfulness(result: QueryResult, unanswerable: bool) -> float:
    if unanswerable:
        return 1.0 if result.answer.refused else 0.0
    if result.answer.refused:
        return 0.0
    cited = set(result.answer.cited_chunk_ids)
    known = {item.chunk_id for item in result.evidence}
    if not cited:
        return 0.0
    return 1.0 if cited.issubset(known) else 0.0


def load_gold(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if not isinstance(cases, list):
        raise ValueError("gold set inválido")
    return cases


def run_harness(mesh: Mesh, workspace_id: str, gold_path: Path, k: int = 5) -> dict[str, object]:
    cases = load_gold(gold_path)
    recalls: list[float] = []
    faiths: list[float] = []
    details: list[dict[str, object]] = []
    for case in cases:
        question = str(case["question"])
        relevant = [str(title) for title in case.get("relevant_doc_titles", [])]  # type: ignore[arg-type]
        unanswerable = bool(case.get("unanswerable", False))
        result = mesh.query(workspace_id, question, hops=1)
        titles = [item.document_title for item in result.evidence]
        rec = recall_at_k(titles, relevant, k)
        faith = faithfulness(result, unanswerable)
        recalls.append(rec)
        faiths.append(faith)
        details.append(
            {
                "id": case.get("id"),
                "recall_at_k": rec,
                "faithfulness": faith,
                "refused": result.answer.refused,
                "titles": titles[:k],
            }
        )
    n = max(len(cases), 1)
    return {
        "cases": len(cases),
        "recall_at_k": sum(recalls) / n,
        "faithfulness": sum(faiths) / n,
        "details": details,
    }
