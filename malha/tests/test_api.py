from fastapi.testclient import TestClient

from mind_shared.api.app import create_app
from mind_shared.config import DEMO_TOKEN, corpus_dir
from mind_shared.types import FeedbackLabel


def _headers(token: str) -> dict[str, str]:
    return {"X-Mind-Token": token}


def test_root_and_health_are_ok(mesh) -> None:
    client = TestClient(create_app(mesh))
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["status"] == "ok"
    assert root.json()["product"] == "mind-shared"
    health = client.get("/health")
    assert health.status_code == 200


def test_query_accepts_workspace_slug(mesh) -> None:
    client = TestClient(create_app(mesh))
    created = client.post(
        "/workspaces", json={"slug": "atlas-norte", "name": "Arquivo Atlas Norte"}
    ).json()
    headers = _headers(created["token"])
    seeded = client.post(f"/workspaces/{created['id']}/seed", headers=headers)
    assert seeded.status_code == 200
    queried = client.post(
        "/workspaces/atlas-norte/query",
        json={"question": "TotalRecall autentica o usuário na Carteira Mind?", "hops": 1},
        headers=headers,
    )
    assert queried.status_code == 200
    assert queried.json()["evidence"]
    asked = client.post(
        "/v1/ask",
        json={
            "workspace_id": "atlas-norte",
            "question": "TotalRecall autentica o usuário na Carteira Mind?",
            "hops": 1,
        },
        headers=headers,
    )
    assert asked.status_code == 200
    docs = client.get("/workspaces/atlas-norte/documents", headers=headers)
    assert docs.status_code == 200
    assert docs.json()


def test_health_and_query_roundtrip(mesh) -> None:
    client = TestClient(create_app(mesh))
    health = client.get("/health")
    assert health.status_code == 200
    created = client.post("/workspaces", json={"slug": "atlas-norte", "name": "Arquivo Atlas Norte"})
    assert created.status_code == 200
    body = created.json()
    workspace_id = body["id"]
    token = body["token"]
    assert token == DEMO_TOKEN
    headers = _headers(token)
    seed = client.post(f"/workspaces/{workspace_id}/seed", headers=headers)
    assert seed.status_code == 200
    assert seed.json()["ingested"]
    queried = client.post(
        f"/workspaces/{workspace_id}/query",
        json={"question": "TotalRecall autentica o usuário na Carteira Mind?", "hops": 1},
        headers=headers,
    )
    assert queried.status_code == 200
    payload = queried.json()
    assert payload["evidence"]
    assert payload["plan"]
    assert payload["verification"]["status"] in {"grounded", "conflict", "insufficient"}
    assert payload["answer"]["grounding_status"] == payload["verification"]["status"]
    asked = client.post(
        "/v1/ask",
        json={
            "workspace_id": workspace_id,
            "question": "TotalRecall autentica o usuário na Carteira Mind?",
            "hops": 1,
        },
        headers=headers,
    )
    assert asked.status_code == 200
    assert asked.json()["plan"]
    chunk_id = payload["evidence"][0]["chunk_id"]
    marked = client.post(
        f"/workspaces/{workspace_id}/feedback",
        headers=headers,
        json={
            "chunk_id": chunk_id,
            "label": FeedbackLabel.USEFUL.value,
            "query_id": payload["query_id"],
        },
    )
    assert marked.status_code == 200
    graph = client.get(f"/workspaces/{workspace_id}/graph", headers=headers)
    assert graph.status_code == 200
    assert graph.json()["entities"]
    assert "conflicts" in graph.json()
    docs = client.get(f"/workspaces/{workspace_id}/documents", headers=headers)
    assert len(docs.json()) >= 1
    assert corpus_dir().name == "corpus"


def test_query_without_token_is_unauthorized(mesh) -> None:
    client = TestClient(create_app(mesh))
    created = client.post("/workspaces", json={"slug": "x", "name": "X"}).json()
    response = client.post(
        f"/workspaces/{created['id']}/query",
        json={"question": "qualquer", "hops": 0},
    )
    assert response.status_code == 401


def test_ingest_rejects_unknown_type(mesh) -> None:
    client = TestClient(create_app(mesh))
    workspace = client.post("/workspaces", json={"slug": "x", "name": "X"}).json()
    response = client.post(
        f"/workspaces/{workspace['id']}/ingest",
        headers=_headers(workspace["token"]),
        files={"file": ("foto.png", b"nope", "image/png")},
    )
    assert response.status_code == 415


def test_openapi_exposes_cycle_contract(mesh) -> None:
    client = TestClient(create_app(mesh))
    spec = client.get("/openapi.json").json()
    assert "/workspaces/{workspace_id}/query" in spec["paths"]
    assert "/v1/ask" in spec["paths"]
    query_schema = spec["components"]["schemas"]["QueryOut"]
    assert "plan" in query_schema["properties"]
    assert "verification" in query_schema["properties"]
