from mind_shared.plan.decompose import decompose
from mind_shared.types import exhaust_plan_kind


def test_plan_keeps_primary_question() -> None:
    steps = decompose("Quem pode acessar dados de produção da carteira?")
    assert steps[0].kind == "lookup"
    assert "produção" in steps[0].objective or "producao" in steps[0].objective.lower()
    assert all(exhaust_plan_kind(step.kind) for step in steps)


def test_plan_adds_hop_and_codes() -> None:
    steps = decompose("O que a norma N-EVID-02 exige após o incidente INC-2025-04?")
    kinds = {step.kind for step in steps}
    texts = " ".join(step.objective for step in steps)
    assert "hop" in kinds
    assert "N-EVID-02" in texts
    assert "INC-2025-04" in texts


def test_plan_detects_compare() -> None:
    steps = decompose("Analistas ledger.reader podem acessar dados de produção da carteira?")
    assert any(step.kind == "compare" for step in steps)
