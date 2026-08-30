from __future__ import annotations

from typing import Protocol

import httpx

from mind_shared.config import composer_backend, composer_model, composer_timeout_seconds, composer_url
from mind_shared.synthesize.grounded import synthesize
from mind_shared.synthesize.llm_shared import (
    COMPOSER_SYSTEM,
    composer_user_prompt,
    grounded_from_llm_text,
)
from mind_shared.synthesize.local_gguf import LocalGgufComposer
from mind_shared.types import ComposerName, Evidence, GroundedAnswer, GroundingStatus, Verification


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
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": COMPOSER_SYSTEM},
                {"role": "user", "content": composer_user_prompt(question, evidence)},
            ],
        }
        try:
            response = httpx.post(
                f"{self.url}/v1/chat/completions",
                json=payload,
                timeout=composer_timeout_seconds(),
            )
            response.raise_for_status()
            text = str(response.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            return self.fallback.compose(question, evidence, verification)
        answer = grounded_from_llm_text(text, evidence, verification)
        if answer is None:
            return self.fallback.compose(question, evidence, verification)
        return answer


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
