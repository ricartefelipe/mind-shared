from pathlib import Path

from mind_shared.config import FAITHFULNESS_FLOOR, corpus_dir
from mind_shared.eval.harness import citation_precision, recall_at_k, run_harness
from mind_shared.types import GroundedAnswer, GroundingStatus, QueryResult


def test_recall_at_k_partial() -> None:
    got = recall_at_k(["Política de acesso a dados", "Glossário"], ["Política de acesso a dados", "Carta"], k=5)
    assert 0.49 < got < 0.51


def test_citation_precision_requires_overlap() -> None:
    answer = GroundedAnswer(
        text="Somente operadores acessam produção [1]",
        refused=False,
        refusal_reason=None,
        cited_chunk_ids=("c1",),
        grounding_status=GroundingStatus.GROUNDED,
    )
    result = QueryResult(
        query_id="q",
        question="quem acessa",
        answer=answer,
        evidence=[],
    )
    assert citation_precision(result, unanswerable=False) == 0.0


def test_harness_on_atlas_gold(atlas) -> None:
    mesh, workspace_id = atlas
    gold = Path(__file__).resolve().parent.parent / "eval" / "gold.json"
    report = run_harness(mesh, workspace_id, gold, k=5)
    assert report["cases"] >= 12
    assert report["recall_at_k"] >= 0.55
    assert report["faithfulness"] >= FAITHFULNESS_FLOOR
    assert report["citation_precision"] >= 0.70
    assert report["passed"] is True
    assert corpus_dir().exists()
    statuses = {item["id"]: item["status"] for item in report["details"]}  # type: ignore[index]
    assert statuses["conflito-reader"] == "conflict"
    assert statuses["salario-marketing"] == "insufficient"
