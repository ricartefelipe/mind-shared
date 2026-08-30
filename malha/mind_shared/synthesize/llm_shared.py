from __future__ import annotations

from mind_shared.types import Evidence, GroundedAnswer, GroundingStatus, Verification

COMPOSER_SYSTEM = (
    "Parafraseie somente as evidências numeradas. "
    "Proibido afirmar fato que não esteja nelas. "
    "Cada frase termina com a citação [n] do trecho usado. "
    "Se houver conflito, relate os dois lados com as fontes e não escolha um. "
    "Se a cobertura for insuficiente, recuse explicitamente."
)


def numbered_evidence(evidence: list[Evidence]) -> str:
    lines: list[str] = []
    for index, item in enumerate(evidence[:6], start=1):
        lines.append(f"[{index}] ({item.document_title}) {item.excerpt}")
    return "\n".join(lines)


def composer_user_prompt(question: str, evidence: list[Evidence]) -> str:
    return f"Pergunta: {question}\n\nEvidências:\n{numbered_evidence(evidence)}"


def cited_from_text(text: str, evidence: list[Evidence]) -> tuple[str, ...]:
    cited: list[str] = []
    for index, item in enumerate(evidence[:6], start=1):
        marker = f"[{index}]"
        if marker in text:
            cited.append(item.chunk_id)
    return tuple(cited)


def grounded_from_llm_text(
    text: str,
    evidence: list[Evidence],
    verification: Verification,
) -> GroundedAnswer | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    cited = cited_from_text(cleaned, evidence)
    if not cited and verification.status is not GroundingStatus.INSUFFICIENT:
        return None
    refused = verification.status is GroundingStatus.INSUFFICIENT
    return GroundedAnswer(
        text=cleaned,
        refused=refused,
        refusal_reason="evidência abaixo do limiar de proveniência" if refused else None,
        cited_chunk_ids=cited,
        grounding_status=verification.status,
    )
