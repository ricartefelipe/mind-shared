from __future__ import annotations

from mind_shared.config import MIN_CONTENT_OVERLAP, MIN_FUSED_SCORE, MIN_OVERLAP_RATIO
from mind_shared.textutil import content_tokens, sentences
from mind_shared.types import Evidence, GroundedAnswer


REFUSAL = (
    "Não há evidência suficiente no arquivo para afirmar isso. "
    "A malha recusa síntese sem trecho, fonte e score."
)


def best_sentence(excerpt: str, question: str) -> str:
    qset = set(content_tokens(question))
    ranked: list[tuple[int, str]] = []
    for sent in sentences(excerpt) or [excerpt]:
        overlap = len(qset.intersection(content_tokens(sent)))
        ranked.append((overlap, sent.strip()))
    ranked.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    return ranked[0][1] if ranked else excerpt.strip()


def synthesize(question: str, evidence: list[Evidence], max_cites: int = 3) -> GroundedAnswer:
    if not evidence:
        return GroundedAnswer(
            text=REFUSAL,
            refused=True,
            refusal_reason="nenhuma evidência recuperada",
            cited_chunk_ids=(),
        )
    top = evidence[0]
    overlap = _overlap_count(question, evidence[:3])
    q_terms = set(content_tokens(question))
    ratio = overlap / len(q_terms) if q_terms else 0.0
    if top.score < MIN_FUSED_SCORE or overlap < MIN_CONTENT_OVERLAP or ratio < MIN_OVERLAP_RATIO:
        return GroundedAnswer(
            text=REFUSAL,
            refused=True,
            refusal_reason="evidência abaixo do limiar de proveniência",
            cited_chunk_ids=(),
        )
    chosen = evidence[:max_cites]
    lines: list[str] = []
    for index, item in enumerate(chosen, start=1):
        sentence = best_sentence(item.excerpt, question)
        lines.append(f"{sentence} [{index}]")
    body = (
        "Síntese fundamentada nas evidências do arquivo (cada afirmação cita trecho, fonte e score):\n\n"
        + " ".join(lines)
    )
    return GroundedAnswer(
        text=body,
        refused=False,
        refusal_reason=None,
        cited_chunk_ids=tuple(item.chunk_id for item in chosen),
    )


def _overlap_count(question: str, evidence: list[Evidence]) -> int:
    qset = set(content_tokens(question))
    corpus = set()
    for item in evidence:
        corpus.update(content_tokens(item.excerpt))
    return len(qset.intersection(corpus))
