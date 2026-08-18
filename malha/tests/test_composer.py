import httpx

from mind_shared.synthesize.composer import ExtractiveComposer, HttpComposer, load_composer
from mind_shared.types import Evidence, GroundingStatus, Verification


def _ev() -> Evidence:
    excerpt = "Somente operadores com papel ledger.admin podem acessar dados de produção da carteira."
    return Evidence(
        chunk_id="c1",
        document_id="doc",
        document_title="Política de acesso a dados",
        source_path="p.md",
        excerpt=excerpt,
        score=0.05,
        hop=0,
        entity_path=(),
        start_char=0,
        end_char=len(excerpt),
        ordinal=0,
    )


def _grounded() -> Verification:
    return Verification(status=GroundingStatus.GROUNDED, coverage=0.8, contradictions=(), notes=("ok",))


def test_load_composer_defaults_extractive(monkeypatch) -> None:
    monkeypatch.delenv("MIND_COMPOSER_URL", raising=False)
    composer = load_composer()
    assert composer.name == "extractive"


def test_http_composer_falls_back_when_endpoint_is_down(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    composer = HttpComposer("http://127.0.0.1:9", "local", ExtractiveComposer())
    answer = composer.compose(
        "Quem pode acessar dados de produção da carteira?",
        [_ev()],
        _grounded(),
    )
    assert answer.cited_chunk_ids
    assert not answer.refused
    assert "[1]" in answer.text
