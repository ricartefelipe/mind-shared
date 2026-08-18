from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from mind_shared.api.schemas import (
    AskIn,
    FeedbackIn,
    GraphConflictOut,
    GraphOut,
    QueryIn,
    QueryOut,
    WorkspaceIn,
    WorkspaceOut,
    query_out,
)
from mind_shared.config import corpus_dir, default_db_path
from mind_shared.engine import Mesh
from mind_shared.eval.harness import run_harness
from mind_shared.ingest.parsers import UnsupportedFormatError
from mind_shared.types import FeedbackLabel


def _ensure_demo_archive(engine: Mesh) -> None:
    if engine.workspaces.list():
        return
    workspace = engine.provision_workspace("atlas-norte", "Arquivo Atlas Norte")
    engine.ingest_corpus(workspace["id"], corpus_dir())


def create_app(mesh: Mesh | None = None) -> FastAPI:
    engine = mesh or Mesh(default_db_path())
    if mesh is None:
        _ensure_demo_archive(engine)
    app = FastAPI(title="Mind Shared", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _authorize(workspace_id: str, token: str | None) -> None:
        if not engine.tokens.verify(workspace_id, token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token ausente ou inválido",
            )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "product": "mind-shared"}

    @app.get("/workspaces")
    def list_workspaces() -> list[dict[str, str]]:
        return engine.workspaces.list()

    @app.post("/workspaces")
    def create_workspace(body: WorkspaceIn) -> WorkspaceOut:
        created = engine.provision_workspace(body.slug, body.name)
        return WorkspaceOut(
            id=created["id"],
            slug=created["slug"],
            name=created["name"],
            created_at=created["created_at"],
            token=created.get("token"),
        )

    @app.get("/workspaces/{workspace_id}/documents")
    def list_documents(
        workspace_id: str,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> list[dict[str, str | int]]:
        _authorize(workspace_id, x_mind_token)
        return engine.documents(workspace_id)

    @app.get("/workspaces/{workspace_id}/graph")
    def graph(
        workspace_id: str,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> GraphOut:
        _authorize(workspace_id, x_mind_token)
        snap = engine.graph_snapshot(workspace_id)
        return GraphOut(
            entities=snap["entities"],
            relations=snap["relations"],
            conflicts=[GraphConflictOut(**item) for item in snap.get("conflicts", [])],
        )

    @app.post(
        "/workspaces/{workspace_id}/ingest",
        responses={status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"description": "formato não suportado"}},
    )
    async def ingest(
        workspace_id: str,
        file: Annotated[UploadFile, File()],
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, str | int]:
        _authorize(workspace_id, x_mind_token)
        data = await file.read()
        try:
            return engine.ingest_upload(workspace_id, file.filename or "arquivo.txt", data)
        except UnsupportedFormatError as exc:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="formato não suportado",
            ) from exc

    @app.post("/workspaces/{workspace_id}/seed")
    def seed(
        workspace_id: str,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, object]:
        _authorize(workspace_id, x_mind_token)
        ingested = engine.ingest_corpus(workspace_id, corpus_dir())
        return {"ingested": ingested}

    @app.post("/workspaces/{workspace_id}/query")
    def query(
        workspace_id: str,
        body: QueryIn,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> QueryOut:
        _authorize(workspace_id, x_mind_token)
        result = engine.query(workspace_id, body.question, hops=body.hops)
        return query_out(result)

    @app.post("/v1/ask")
    def ask(
        body: AskIn,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> QueryOut:
        _authorize(body.workspace_id, x_mind_token)
        result = engine.query(body.workspace_id, body.question, hops=body.hops)
        return query_out(result)

    @app.post(
        "/workspaces/{workspace_id}/feedback",
        responses={status.HTTP_400_BAD_REQUEST: {"description": "feedback inválido"}},
    )
    def feedback(
        workspace_id: str,
        body: FeedbackIn,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, str]:
        _authorize(workspace_id, x_mind_token)
        try:
            feedback_id = engine.mark_feedback(
                workspace_id,
                body.chunk_id,
                FeedbackLabel(body.label),
                body.query_id,
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="feedback inválido",
            ) from exc
        return {"feedback_id": feedback_id}

    @app.post("/workspaces/{workspace_id}/eval")
    def evaluate(
        workspace_id: str,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, object]:
        _authorize(workspace_id, x_mind_token)
        gold = Path(__file__).resolve().parent.parent.parent / "eval" / "gold.json"
        return run_harness(engine, workspace_id, gold)

    return app
