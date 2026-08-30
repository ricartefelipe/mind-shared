from __future__ import annotations

import threading
from typing import Any, Protocol

from mind_shared.config import composer_gguf_path
from mind_shared.synthesize.llm_shared import (
    COMPOSER_SYSTEM,
    composer_user_prompt,
    grounded_from_llm_text,
)
from mind_shared.types import ComposerName, Evidence, GroundedAnswer, Verification

_lock = threading.Lock()
_model: Any = None


class ComposerFallback(Protocol):
    def compose(
        self,
        question: str,
        evidence: list[Evidence],
        verification: Verification,
    ) -> GroundedAnswer: ...


def _load_llama():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python não instalado; rode make install-malha-ai"
            ) from exc
        path = composer_gguf_path()
        if not path.is_file():
            raise FileNotFoundError(
                f"modelo GGUF não encontrado: {path}; rode make ai-up"
            )
        _model = Llama(
            model_path=str(path),
            n_ctx=4096,
            n_threads=0,
            verbose=False,
        )
        return _model


class LocalGgufComposer:
    name: ComposerName = "local"

    def __init__(self, fallback: ComposerFallback) -> None:
        self.fallback = fallback

    def compose(
        self,
        question: str,
        evidence: list[Evidence],
        verification: Verification,
    ) -> GroundedAnswer:
        messages = [
            {"role": "system", "content": COMPOSER_SYSTEM},
            {"role": "user", "content": composer_user_prompt(question, evidence)},
        ]
        try:
            llm = _load_llama()
            response = llm.create_chat_completion(
                messages=messages,
                temperature=0.0,
                max_tokens=512,
            )
            text = str(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError, OSError, RuntimeError):
            return self.fallback.compose(question, evidence, verification)
        answer = grounded_from_llm_text(text, evidence, verification)
        if answer is None:
            return self.fallback.compose(question, evidence, verification)
        return answer
