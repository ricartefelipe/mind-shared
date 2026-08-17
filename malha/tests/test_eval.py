from pathlib import Path

from mind_shared.config import corpus_dir
from mind_shared.eval.harness import recall_at_k, run_harness


def test_recall_at_k_partial() -> None:
    got = recall_at_k(["Política de acesso a dados", "Glossário"], ["Política de acesso a dados", "Carta"], k=5)
    assert 0.49 < got < 0.51


def test_harness_on_atlas_gold(atlas) -> None:
    mesh, workspace_id = atlas
    gold = Path(__file__).resolve().parent.parent / "eval" / "gold.json"
    report = run_harness(mesh, workspace_id, gold, k=5)
    assert report["cases"] == 8
    assert report["recall_at_k"] >= 0.6
    assert report["faithfulness"] >= 0.75
    assert corpus_dir().exists()
