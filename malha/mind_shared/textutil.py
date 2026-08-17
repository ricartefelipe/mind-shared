from __future__ import annotations

import re
import unicodedata

_TOKEN = re.compile(r"[a-z0-9à-ü]+", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n{2,}")

STOPWORDS = frozenset(
    {
        "a",
        "ao",
        "aos",
        "as",
        "ate",
        "com",
        "como",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "entre",
        "era",
        "essa",
        "esse",
        "esta",
        "este",
        "foi",
        "ha",
        "isso",
        "mais",
        "nao",
        "nem",
        "o",
        "os",
        "ou",
        "para",
        "pela",
        "pelo",
        "por",
        "que",
        "se",
        "sem",
        "ser",
        "seu",
        "sua",
        "um",
        "uma",
        "uns",
        "umas",
    }
)


def fold(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(fold(text))


def content_tokens(text: str) -> list[str]:
    return [tok for tok in tokens(text) if tok not in STOPWORDS and len(tok) > 1]


def sentences(text: str) -> list[str]:
    parts = _SENTENCE.split(text.strip())
    return [part.strip() for part in parts if part.strip()]
