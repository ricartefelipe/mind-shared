from fastapi.testclient import TestClient

from mind_shared.api.app import create_app
from mind_shared.config import corpus_dir
from mind_shared.types import FeedbackLabel


def test_health_and_query_roundtrip(mesh) -> None:
    client = TestClient(create_app(mesh))
    health = client.get("/health")
    assert health.status_code == 200
    created = client.post("/workspaces", json={"slug": "atlas-norte", "name": "Arquivo Atlas Norte"})
    assert created.status_code == 200
    workspace_id = created.json()["id"]
    seed = client.post(f"/workspaces/{workspace_id}/seed")
    assert seed.status_code == 200
    assert seed.json()["ingested"]
    queried = client.post(
        f"/workspaces/{workspace_id}/query",
        json={"question": "TotalRecall autentica o usuário na Carteira Mind?", "hops": 1},
    )
    assert queried.status_code == 200
    body = queried.json()
    assert body["evidence"]
    assert "answer" in body
    chunk_id = body["evidence"][0]["chunk_id"]
    marked = client.post(
        f"/workspaces/{workspace_id}/feedback",
        json={
            "chunk_id": chunk_id,
            "label": FeedbackLabel.USEFUL.value,
            "query_id": body["query_id"],
        },
    )
    assert marked.status_code == 200
    graph = client.get(f"/workspaces/{workspace_id}/graph")
    assert graph.status_code == 200
    assert graph.json()["entities"]
    docs = client.get(f"/workspaces/{workspace_id}/documents")
    assert len(docs.json()) >= 1
    assert corpus_dir().name == "corpus"


def test_ingest_rejects_unknown_type(mesh) -> None:
    client = TestClient(create_app(mesh))
    workspace = client.post("/workspaces", json={"slug": "x", "name": "X"}).json()
    response = client.post(
        f"/workspaces/{workspace['id']}/ingest",
        files={"file": ("foto.png", b"nope", "image/png")},
    )
    assert response.status_code == 415
