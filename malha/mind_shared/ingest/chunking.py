from __future__ import annotations

from dataclasses import dataclass, field

from mind_shared.config import CHUNK_OVERLAP_CHARS, CHUNK_TARGET_CHARS
from mind_shared.textutil import sentences
from mind_shared.types import ChunkDraft


@dataclass
class _Window:
    target: int
    overlap: int
    packed: list[ChunkDraft] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)
    start: int = 0
    ordinal: int = 0

    def flush(self, end: int) -> None:
        body = " ".join(self.parts).strip()
        if not body:
            self.parts = []
            return
        self.packed.append(
            ChunkDraft(
                ordinal=self.ordinal,
                text=body,
                start_char=self.start,
                end_char=end,
            )
        )
        self.ordinal += 1
        self._retain(body, end)

    def _retain(self, body: str, end: int) -> None:
        if self.overlap <= 0:
            self.parts = []
            self.start = end
            return
        keep = body[-self.overlap :]
        self.parts = [keep]
        self.start = max(self.start, end - len(keep))

    def push(self, unit: str, start: int) -> None:
        candidate = (" ".join([*self.parts, unit])).strip()
        if self.parts and len(candidate) > self.target:
            self.flush(start)
        if not self.parts:
            self.start = start
        self.parts.append(unit)


def chunk_text(
    text: str,
    target: int = CHUNK_TARGET_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[ChunkDraft]:
    window = _Window(target=target, overlap=overlap)
    _feed(window, text, _units(text))
    if window.parts:
        window.flush(len(text))
    return window.packed


def _units(text: str) -> list[str]:
    found = sentences(text)
    if found:
        return found
    stripped = text.strip()
    if stripped:
        return [stripped]
    return []


def _feed(window: _Window, text: str, units: list[str]) -> None:
    offset = 0
    for unit in units:
        start = text.find(unit, offset)
        if start < 0:
            start = offset
        offset = start + len(unit)
        window.push(unit, start)
