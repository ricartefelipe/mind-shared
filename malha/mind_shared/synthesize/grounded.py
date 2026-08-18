from __future__ import annotations

from mind_shared.config import MIN_CONTENT_OVERLAP, MIN_FUSED_SCORE, MIN_OVERLAP_RATIO
from mind_shared.textutil import content_tokens, sentences
from mind_shared.types import (
    Evidence,
    GroundedAnswer,
    GroundingStatus,
    Verification,
)


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


def synthesize(
    question: str,
    evidence: list[Evidence],
    verification: Verification | None = None,
    max_cites: int = 3,
) -> GroundedAnswer:
    status = verification.status if verification else _legacy_status(question, evidence)
    if status is GroundingStatus.INSUFFICIENT or not evidence:
        reason = "nenhuma evidência recuperada"
        if evidence:
            reason = "evidência abaixo do limiar de proveniência"
        if verification and verification.notes:
            reason = verification.notes[0]
        return GroundedAnswer(
            text=REFUSAL,
            refused=True,
            refusal_reason=reason,
            cited_chunk_ids=(),
            grounding_status=GroundingStatus.INSUFFICIENT,
        )
    if status is GroundingStatus.CONFLICT:
        return _compose_conflict(question, evidence, verification)
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
        grounding_status=GroundingStatus.GROUNDED,
    )


def _compose_conflict(
    question: str,
    evidence: list[Evidence],
    verification: Verification | None,
) -> GroundedAnswer:
    pair = _conflict_pair(evidence, verification)
    lines = [
        "O arquivo registra posições incompatíveis. A malha não escolhe um lado; relata as fontes.",
        "",
    ]
    cited: list[str] = []
    labels = ("A", "B")
    for index, item in enumerate(pair, start=1):
        sentence = best_sentence(item.excerpt, question)
        lines.append(f"[{labels[index - 1]}] {sentence} [{index}] — {item.document_title}")
        cited.append(item.chunk_id)
    return GroundedAnswer(
        text="\n".join(lines),
        refused=False,
        refusal_reason=None,
        cited_chunk_ids=tuple(cited),
        grounding_status=GroundingStatus.CONFLICT,
    )


def _conflict_pair(evidence: list[Evidence], verification: Verification | None) -> list[Evidence]:
    sides = _sides_from_verification(verification, {item.chunk_id: item for item in evidence})
    unique = _first_unique([*sides, *evidence], 2)
    if len(unique) < 2:
        return evidence[:2]
    return unique


def _sides_from_verification(
    verification: Verification | None,
    by_id: dict[str, Evidence],
) -> list[Evidence]:
    if verification is None:
        return []
    sides: list[Evidence] = []
    for item in verification.contradictions:
        left = by_id.get(item.left_chunk_id)
        right = by_id.get(item.right_chunk_id)
        if left is not None:
            sides.append(left)
        if right is not None:
            sides.append(right)
        if len(sides) >= 2:
            break
    return sides


def _first_unique(items: list[Evidence], limit: int) -> list[Evidence]:
    unique: list[Evidence] = []
    seen: set[str] = set()
    for item in items:
        if item.chunk_id in seen:
            continue
        seen.add(item.chunk_id)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def _legacy_status(question: str, evidence: list[Evidence]) -> GroundingStatus:
    if not evidence:
        return GroundingStatus.INSUFFICIENT
    top = evidence[0]
    overlap = _overlap_count(question, evidence[:3])
    q_terms = set(content_tokens(question))
    ratio = overlap / len(q_terms) if q_terms else 0.0
    if top.score < MIN_FUSED_SCORE or overlap < MIN_CONTENT_OVERLAP or ratio < MIN_OVERLAP_RATIO:
        return GroundingStatus.INSUFFICIENT
    return GroundingStatus.GROUNDED


def _overlap_count(question: str, evidence: list[Evidence]) -> int:
    qset = set(content_tokens(question))
    corpus = set()
    for item in evidence:
        corpus.update(content_tokens(item.excerpt))
    return len(qset.intersection(corpus))
