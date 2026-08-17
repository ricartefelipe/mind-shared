from __future__ import annotations

from mind_shared.config import CHUNK_OVERLAP_CHARS, CHUNK_TARGET_CHARS
from mind_shared.textutil import sentences
from mind_shared.types import ChunkDraft


def chunk_text(
    text: str,
    target: int = CHUNK_TARGET_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[ChunkDraft]:
    packed: list[ChunkDraft] = []
    units = sentences(text) or ([text.strip()] if text.strip() else [])
    buf: list[str] = []
    buf_start = 0
    cursor = 0
    ordinal = 0

    def flush(end: int) -> None:
        nonlocal buf, buf_start, ordinal
        body = " ".join(buf).strip()
        if not body:
            buf = []
            return
        packed.append(
            ChunkDraft(
                ordinal=ordinal,
                text=body,
                start_char=buf_start,
                end_char=end,
            )
        )
        ordinal += 1
        if overlap <= 0 or not body:
            buf = []
            buf_start = end
            return
        keep = body[-overlap:]
        buf = [keep]
        buf_start = max(buf_start, end - len(keep))

    for unit in units:
        start = text.find(unit, cursor)
        if start < 0:
            start = cursor
        end = start + len(unit)
        cursor = end
        candidate = (" ".join(buf + [unit])).strip()
        if buf and len(candidate) > target:
            flush(start)
        if not buf:
            buf_start = start
        buf.append(unit)

    if buf:
        flush(len(text))
    return packed
