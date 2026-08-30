from __future__ import annotations

from typing import Protocol

import httpx

from mind_shared.config import composer_backend, composer_model, composer_timeout_seconds, composer_url
from mind_shared.synthesize.local_gguf import LocalGgufComposer
from mind_shared.synthesize.grounded import synthesize
from mind_shared.types import ComposerName, Evidence, GroundedAnswer, GroundingStatus, Verification

_SYSTEM = (
    "Parafraseie somente as evidências numeradas. "
    "Proibido afirmar fato que não esteja nelas. "
    "Cada frase termina com a citação [n] do trecho usado. "
    "Se houver conflito, relate os dois lados com as fontes e não escolha um. "
    "Se a cobertura for insuficiente, recuse explicitamente."
)


class Composer(Protocol):
    name: ComposerName

    def compose(
        self,
        question: str,
        evidence: list[Evidence],
        verification: Verification,
    ) -> GroundedAnswer: ...


class ExtractiveComposer:
    name: ComposerName = "extractive"

    def compose(
        self,
        question: str,
        evidence: list[Evidence],
        verification: Verification,
    ) -> GroundedAnswer:
        return synthesize(question, evidence, verification)


class HttpComposer:
    name: ComposerName = "http"

    def __init__(self, url: str, model: str, fallback: Composer) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.fallback = fallback

    def compose(
        self,
        question: str,
        evidence: list[Evidence],
        verification: Verification,
    ) -> GroundedAnswer:
        numbered = _numbered(evidence)
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": f"Pergunta: {question}\n\nEvidências:\n{numbered}",
                },
            ],
        }
        try:
            response = httpx.post(
                f"{self.url}/v1/chat/completions",
                json=payload,
                timeout=composer_timeout_seconds(),
            )
            response.raise_for_status()
            text = str(response.json()["choices"][0]["message"]["content"]).strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            return self.fallback.compose(question, evidence, verification)
        if not text:
            return self.fallback.compose(question, evidence, verification)
        cited = _cited_from_text(text, evidence)
        if not cited and verification.status is not GroundingStatus.INSUFFICIENT:
            return self.fallback.compose(question, evidence, verification)
        refused = verification.status is GroundingStatus.INSUFFICIENT
        return GroundedAnswer(
            text=text,
            refused=refused,
            refusal_reason="evidência abaixo do limiar de proveniência" if refused else None,
            cited_chunk_ids=cited,
            grounding_status=verification.status,
        )


def load_composer() -> Composer:
    fallback = ExtractiveComposer()
    backend = composer_backend()
    if backend == "local":
        return LocalGgufComposer(fallback)
    url = composer_url()
    if url:
        return HttpComposer(url, composer_model(), fallback)
    if backend == "http":
        return fallback
    return fallback


def _numbered(evidence: list[Evidence]) -> str:
    lines: list[str] = []
    for index, item in enumerate(evidence[:6], start=1):
        lines.append(f"[{index}] ({item.document_title}) {item.excerpt}")
    return "\n".join(lines)


def _cited_from_text(text: str, evidence: list[Evidence]) -> tuple[str, ...]:
    cited: list[str] = []
    for index, item in enumerate(evidence[:6], start=1):
        marker = f"[{index}]"
        if marker in text:
            cited.append(item.chunk_id)
    return tuple(cited)
