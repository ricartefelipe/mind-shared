from mind_shared.types import Evidence, GroundingStatus, Verification
from mind_shared.verify.engine import verify


def _ev(chunk: str, excerpt: str, score: float = 0.05) -> Evidence:
    return Evidence(
        chunk_id=chunk,
        document_id="doc",
        document_title="Doc",
        source_path="doc.md",
        excerpt=excerpt,
        score=score,
        hop=0,
        entity_path=(),
        start_char=0,
        end_char=len(excerpt),
        ordinal=0,
    )


def test_verify_insufficient_without_evidence() -> None:
    result = verify("qualquer pergunta", [])
    assert result.status is GroundingStatus.INSUFFICIENT


def test_verify_marks_conflict_on_reader_access() -> None:
    left = _ev(
        "c1",
        "Analistas com papel ledger.reader podem acessar dados de produção da carteira com aprovação verbal.",
    )
    right = _ev(
        "c2",
        "Analistas com papel ledger.reader não podem acessar dados de produção da carteira.",
    )
    result: Verification = verify(
        "Analistas ledger.reader podem acessar dados de produção da carteira?",
        [left, right],
    )
    assert result.status is GroundingStatus.CONFLICT
    assert result.contradictions


def test_verify_grounded_when_consistent() -> None:
    excerpt = (
        "Somente operadores com papel ledger.admin podem acessar dados de produção da carteira."
    )
    result = verify(
        "Quem pode acessar dados de produção da carteira?",
        [_ev("c1", excerpt), _ev("c2", excerpt + " Ticket obrigatório.")],
    )
    assert result.status is GroundingStatus.GROUNDED
