from __future__ import annotations

import threading
from typing import Any

from mind_shared.config import composer_gguf_path
from mind_shared.types import ComposerName, Evidence, GroundedAnswer, GroundingStatus, Verification

_SYSTEM = (
    "Parafraseie somente as evidências numeradas. "
    "Proibido afirmar fato que não esteja nelas. "
    "Cada frase termina com a citação [n] do trecho usado. "
    "Se houver conflito, relate os dois lados com as fontes e não escolha um. "
    "Se a cobertura for insuficiente, recuse explicitamente."
)

_lock = threading.Lock()
_model: Any = None


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

    def __init__(self, fallback: "ExtractiveComposer") -> None:
        self.fallback = fallback

    def compose(
        self,
        question: str,
        evidence: list[Evidence],
        verification: Verification,
    ) -> GroundedAnswer:
        numbered = _numbered(evidence)
        messages = [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": f"Pergunta: {question}\n\nEvidências:\n{numbered}",
            },
        ]
        try:
            llm = _load_llama()
            response = llm.create_chat_completion(
                messages=messages,
                temperature=0.0,
                max_tokens=512,
            )
            text = str(response["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError, ValueError, OSError, RuntimeError):
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
