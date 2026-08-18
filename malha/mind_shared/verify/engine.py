from __future__ import annotations

from mind_shared.config import MIN_FUSED_SCORE, MIN_OVERLAP_RATIO
from mind_shared.textutil import content_tokens, fold, sentences
from mind_shared.types import Contradiction, Evidence, GroundingStatus, Verification, exhaust_grounding_status

_POLES: tuple[tuple[str, str], ...] = (
    ("podem acessar dados de producao", "nao podem acessar dados de producao"),
    ("pode acessar dados de producao", "nao pode acessar dados de producao"),
    ("permite leitura", "revoga"),
    ("autoriza chaves pix de producao em mocks", "nao entram em mocks"),
    ("pode exibir payload demonstrativo", "recusa payload demonstrativo"),
    ("sem ticket", "exige ticket"),
    ("aprovacao verbal", "ticket obrigatorio"),
    ("permanecem no arquivo por 12 meses", "permanece no arquivo por 24 meses"),
    ("permanecem no arquivo por 12 meses", "permanecem no arquivo por 24 meses"),
)

_SUBJECTS: tuple[str, ...] = (
    "ledger.reader",
    "dados de producao",
    "producao da carteira",
    "chaves pix de producao",
    "payload demonstrativo",
    "c-acesso-2019",
    "c-pix-2023",
    "dec-2026-03",
    "p-acesso-01",
)


def verify(
    question: str,
    evidence: list[Evidence],
    graph_conflicts: tuple[Contradiction, ...] = (),
) -> Verification:
    coverage = _coverage(question, evidence)
    text_conflicts = _text_conflicts(evidence)
    merged = _dedupe((*text_conflicts, *graph_conflicts))
    notes: list[str] = []
    status: GroundingStatus
    if not evidence:
        status = GroundingStatus.INSUFFICIENT
        notes.append("nenhuma evidência recuperada")
    elif evidence[0].score < MIN_FUSED_SCORE or coverage < MIN_OVERLAP_RATIO:
        status = GroundingStatus.INSUFFICIENT
        notes.append("cobertura ou score abaixo do limiar de proveniência")
    elif merged:
        status = GroundingStatus.CONFLICT
        notes.append("evidências incompatíveis no mesmo sujeito")
    else:
        status = GroundingStatus.GROUNDED
        notes.append("trechos cobrem a pergunta sem contradição detectada")
    _ = exhaust_grounding_status(status)
    return Verification(
        status=status,
        coverage=coverage,
        contradictions=merged,
        notes=tuple(notes),
    )


def _coverage(question: str, evidence: list[Evidence]) -> float:
    qset = set(content_tokens(question))
    if not qset:
        return 0.0
    corpus: set[str] = set()
    for item in evidence[:8]:
        corpus.update(content_tokens(item.excerpt))
    return len(qset.intersection(corpus)) / len(qset)


def _text_conflicts(evidence: list[Evidence]) -> tuple[Contradiction, ...]:
    found: list[Contradiction] = []
    for i, left in enumerate(evidence):
        left_fold = fold(left.excerpt)
        for right in evidence[i + 1 :]:
            right_fold = fold(right.excerpt)
            subject = _shared_subject(left_fold, right_fold)
            if not subject:
                continue
            pole = _opposing_poles(left_fold, right_fold)
            if not pole:
                continue
            found.append(
                Contradiction(
                    left_chunk_id=left.chunk_id,
                    right_chunk_id=right.chunk_id,
                    subject=subject,
                    left_claim=_claim(left.excerpt),
                    right_claim=_claim(right.excerpt),
                    reason=f"predicados incompatíveis ({pole[0]} / {pole[1]})",
                )
            )
    return tuple(found)


def _shared_subject(left: str, right: str) -> str | None:
    for key in _SUBJECTS:
        if key in left and key in right:
            return key
    return None


def _opposing_poles(left: str, right: str) -> tuple[str, str] | None:
    for a, b in _POLES:
        if (a in left and b in right) or (b in left and a in right):
            return a, b
    return None


def _claim(excerpt: str) -> str:
    parts = sentences(excerpt) or [excerpt]
    return parts[0].strip()[:240]


def _dedupe(items: tuple[Contradiction, ...]) -> tuple[Contradiction, ...]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[Contradiction] = []
    for item in items:
        key = tuple(sorted((item.left_chunk_id, item.right_chunk_id)) + [item.subject])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return tuple(unique)
