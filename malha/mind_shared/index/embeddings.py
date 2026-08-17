from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np

from mind_shared.config import DENSE_DIM
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
            digest = hashlib.md5(gram.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec


def load_backend(name: str = "hash") -> EmbeddingBackend:
    if name in {"hash", "hashing", "local"}:
        return HashingTrickEmbedding()
    if name in {"sentence", "minilm", "transformers"}:
        return _sentence_backend()
    raise ValueError(f"backend de embedding desconhecido: {name}")


def _sentence_backend() -> EmbeddingBackend:
    if SentenceTransformer is None:
        raise RuntimeError(
            "sentence-transformers não instalado; use o backend hash"
        )

    class SentenceEmbedding:
        dim = DENSE_DIM

        def __init__(self) -> None:
            self._model = SentenceTransformer("all-MiniLM-L6-v2")

        def encode(self, text: str) -> np.ndarray:
            vector = self._model.encode(text, normalize_embeddings=True)
            return np.asarray(vector, dtype=np.float32)

    return SentenceEmbedding()
