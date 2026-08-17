from mind_shared.synthesize.grounded import REFUSAL, synthesize
from mind_shared.types import Evidence, GroundedAnswer


def _ev(chunk: str, excerpt: str, score: float) -> Evidence:
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


def test_refuses_without_evidence() -> None:
    answer = synthesize("qualquer pergunta", [])
    assert answer.refused
    assert answer.text == REFUSAL
    assert answer.cited_chunk_ids == ()


def test_refuses_low_score_or_no_overlap() -> None:
    answer = synthesize(
        "qual o salário secreto do diretor",
        [_ev("c1", "O PIX valida chave CPF e e-mail.", 0.001)],
    )
    assert answer.refused


def test_cites_only_provided_evidence() -> None:
    excerpt = (
        "Somente operadores com papel ledger.admin podem acessar dados de produção da carteira."
    )
    answer: GroundedAnswer = synthesize(
        "Quem pode acessar dados de produção da carteira?",
        [_ev("c1", excerpt, 0.05), _ev("c2", excerpt + " Ticket obrigatório.", 0.04)],
    )
    assert not answer.refused
    assert set(answer.cited_chunk_ids) <= {"c1", "c2"}
    assert "[1]" in answer.text
