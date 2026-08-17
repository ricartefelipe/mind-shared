from __future__ import annotations

import json
from pathlib import Path

from mind_shared.config import FAITHFULNESS_FLOOR
from mind_shared.engine import Mesh
from mind_shared.textutil import content_tokens
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


def citation_precision(result: QueryResult, unanswerable: bool) -> float:
    if unanswerable or result.answer.refused:
        return 1.0 if not result.answer.cited_chunk_ids else 0.0
    cited = result.answer.cited_chunk_ids
    if not cited:
        return 0.0
    known = {item.chunk_id: item for item in result.evidence}
    answer_toks = set(content_tokens(result.answer.text))
    ok = 0
    for chunk_id in cited:
        item = known.get(chunk_id)
        if item is None:
            continue
        excerpt_toks = set(content_tokens(item.excerpt))
        if excerpt_toks.intersection(answer_toks):
            ok += 1
    return ok / len(cited)


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
    precisions: list[float] = []
    details: list[dict[str, object]] = []
    for case in cases:
        question = str(case["question"])
        relevant = [str(title) for title in case.get("relevant_doc_titles", [])]  # type: ignore[arg-type]
        unanswerable = bool(case.get("unanswerable", False))
        result = mesh.query(workspace_id, question, hops=1)
        titles = [item.document_title for item in result.evidence]
        rec = recall_at_k(titles, relevant, k)
        faith = faithfulness(result, unanswerable)
        precision = citation_precision(result, unanswerable)
        recalls.append(rec)
        faiths.append(faith)
        precisions.append(precision)
        status = result.verification.status.value if result.verification else None
        details.append(
            {
                "id": case.get("id"),
                "recall_at_k": rec,
                "faithfulness": faith,
                "citation_precision": precision,
                "refused": result.answer.refused,
                "status": status,
                "titles": titles[:k],
            }
        )
    n = max(len(cases), 1)
    faith_mean = sum(faiths) / n
    return {
        "cases": len(cases),
        "recall_at_k": sum(recalls) / n,
        "faithfulness": faith_mean,
        "citation_precision": sum(precisions) / n,
        "faithfulness_floor": FAITHFULNESS_FLOOR,
        "passed": faith_mean >= FAITHFULNESS_FLOOR,
        "details": details,
    }
