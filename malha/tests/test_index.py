from mind_shared.index.embeddings import HashingTrickEmbedding
from mind_shared.index.hybrid import reciprocal_rank_fusion
from mind_shared.types import RankedHit


def test_hashing_embedding_is_deterministic_and_normalized() -> None:
    backend = HashingTrickEmbedding()
    a = backend.encode("Carteira Mind PIX evidência")
    b = backend.encode("Carteira Mind PIX evidência")
    assert a.shape == b.shape
    assert abs(float(a @ b) - 1.0) < 1e-5


def test_related_texts_outrank_unrelated() -> None:
    backend = HashingTrickEmbedding()
    query = backend.encode("quem acessa dados de produção da carteira")
    close = backend.encode("somente operadores acessam dados de produção da carteira")
    far = backend.encode("receita de bolo de chocolate com cobertura")
    assert float(query @ close) > float(query @ far)


def test_rrf_prefers_consensus() -> None:
    sparse = [
        RankedHit("a", 10.0, "sparse"),
        RankedHit("b", 9.0, "sparse"),
    ]
    dense = [
        RankedHit("b", 0.9, "dense"),
        RankedHit("c", 0.8, "dense"),
    ]
    fused = reciprocal_rank_fusion(sparse, dense)
    assert fused[0].chunk_id == "b"
    assert fused[0].channel == "fused"
