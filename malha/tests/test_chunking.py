from mind_shared.ingest.chunking import chunk_text
from mind_shared.ingest.parsers import UnsupportedFormatError, parse_bytes


def test_chunking_overlap_and_ordinals() -> None:
    text = "Primeira sentença sobre a Carteira Mind. " * 8 + "Segunda ideia sobre PIX e evidência. " * 8
    chunks = chunk_text(text, target=180, overlap=40)
    assert len(chunks) >= 2
    assert [item.ordinal for item in chunks] == list(range(len(chunks)))
    assert all(item.text for item in chunks)
    assert chunks[0].start_char == 0
    assert chunks[-1].end_char <= len(text)


def test_parse_markdown_title() -> None:
    parsed = parse_bytes("politica.md", b"# Politica X\n\nCorpo da norma.")
    assert parsed.title == "Politica X"
    assert parsed.mime == "text/markdown"


def test_reject_unknown_format() -> None:
    try:
        parse_bytes("foto.png", b"\x89PNG")
    except UnsupportedFormatError:
        return
    raise AssertionError("esperava formato rejeitado")
