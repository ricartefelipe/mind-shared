from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from mind_shared.types import ParsedDocument

SUPPORTED = {".pdf", ".md", ".markdown", ".txt", ".text"}


class UnsupportedFormatError(ValueError):
    pass


def checksum_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def parse_path(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    data = path.read_bytes()
    return parse_bytes(path.name, data, source_path=str(path), suffix=suffix)


def parse_bytes(
    filename: str,
    data: bytes,
    source_path: str | None = None,
    suffix: str | None = None,
) -> ParsedDocument:
    suffix = (suffix or Path(filename).suffix).lower()
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages)
        mime = "application/pdf"
    elif suffix in {".md", ".markdown"}:
        text = data.decode("utf-8")
        mime = "text/markdown"
    elif suffix in {".txt", ".text"}:
        text = data.decode("utf-8")
        mime = "text/plain"
    else:
        raise UnsupportedFormatError(f"formato não suportado: {suffix}")
    title = _title_from(Path(filename), text)
    return ParsedDocument(
        title=title,
        text=text,
        mime=mime,
        source_path=source_path or filename,
    )


def document_checksum(parsed: ParsedDocument) -> str:
    payload = f"{parsed.title}\n{parsed.text}".encode("utf-8")
    return checksum_bytes(payload)


def stable_id(*parts: str) -> str:
    joined = "|".join(parts).encode("utf-8")
    return sha256(joined).hexdigest()


def _title_from(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped:
            return stripped[:120]
    return path.stem.replace("-", " ").replace("_", " ")
