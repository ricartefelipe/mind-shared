from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Protocol

import numpy as np

from mind_shared.config import DENSE_DIM, embedding_backend_name, embedding_model_name
from mind_shared.textutil import content_tokens, tokens

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


class EmbeddingBackend(Protocol):
    dim: int

    def encode(self, text: str) -> np.ndarray: ...


class HashingTrickEmbedding:
    dim = DENSE_DIM

    def encode(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        toks = content_tokens(text) or tokens(text)
        grams = list(toks)
        joined = "".join(toks)
        for i in range(max(0, len(joined) - 2)):
            grams.append(joined[i : i + 3])
        for i, gram in enumerate(toks[:-1]):
            grams.append(f"{gram}_{toks[i + 1]}")
        for gram in grams:
            digest = hashlib.sha256(gram.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec


class SentenceEmbedding:
    dim = DENSE_DIM

    def __init__(self, model_name: str | None = None) -> None:
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers não instalado; use o backend hash")
        chosen = model_name or embedding_model_name() or "all-MiniLM-L6-v2"
        self._model = SentenceTransformer(chosen)

    def encode(self, text: str) -> np.ndarray:
        vector = self._model.encode(text, normalize_embeddings=True)
        return np.asarray(vector, dtype=np.float32)


def _hash_factory() -> EmbeddingBackend:
    return HashingTrickEmbedding()


def _sentence_factory() -> EmbeddingBackend:
    return SentenceEmbedding()


BACKEND_FACTORIES: dict[str, Callable[[], EmbeddingBackend]] = {
    "hash": _hash_factory,
    "hashing": _hash_factory,
    "local": _hash_factory,
}

if SentenceTransformer is not None:
    BACKEND_FACTORIES["sentence"] = _sentence_factory
    BACKEND_FACTORIES["minilm"] = _sentence_factory
    BACKEND_FACTORIES["transformers"] = _sentence_factory


def load_backend(name: str | None = None) -> EmbeddingBackend:
    requested = (name or embedding_backend_name() or "").strip().lower()
    model = embedding_model_name()
    if not requested:
        if model or SentenceTransformer is not None:
            requested = "sentence"
        else:
            requested = "hash"
    factory = BACKEND_FACTORIES.get(requested)
    if factory is None:
        if requested in {"sentence", "minilm", "transformers"}:
            return HashingTrickEmbedding()
        raise ValueError(f"backend de embedding desconhecido: {requested}")
    try:
        return factory()
    except (RuntimeError, OSError, ValueError):
        if requested in {"sentence", "minilm", "transformers"}:
            return HashingTrickEmbedding()
        raise
