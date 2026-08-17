from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mind_shared.config import GRAPH_HOPS_DEFAULT, corpus_dir, default_db_path
from mind_shared.engine import Mesh
from mind_shared.eval.harness import run_harness
from mind_shared.ingest.parsers import UnsupportedFormatError
from mind_shared.types import Evidence, FeedbackLabel, QueryResult


class WorkspaceIn(BaseModel):
    slug: str
    name: str


class QueryIn(BaseModel):
    question: str
    hops: int = Field(default=GRAPH_HOPS_DEFAULT, ge=0, le=3)


class FeedbackIn(BaseModel):
    chunk_id: str
    label: FeedbackLabel
    query_id: str | None = None


def _evidence_payload(item: Evidence) -> dict[str, object]:
    return {
        "chunk_id": item.chunk_id,
        "document_id": item.document_id,
        "document_title": item.document_title,
        "source_path": item.source_path,
        "excerpt": item.excerpt,
        "score": item.score,
        "hop": item.hop,
        "entity_path": list(item.entity_path),
        "start_char": item.start_char,
        "end_char": item.end_char,
        "ordinal": item.ordinal,
    }


def _query_payload(result: QueryResult) -> dict[str, object]:
    return {
        "query_id": result.query_id,
        "question": result.question,
        "answer": {
            "text": result.answer.text,
            "refused": result.answer.refused,
            "refusal_reason": result.answer.refusal_reason,
            "cited_chunk_ids": list(result.answer.cited_chunk_ids),
        },
        "evidence": [_evidence_payload(item) for item in result.evidence],
    }


def _ensure_demo_archive(engine: Mesh) -> None:
    if engine.workspaces.list():
        return
    workspace = engine.workspaces.create("atlas-norte", "Arquivo Atlas Norte")
    engine.ingest_corpus(workspace["id"], corpus_dir())


def create_app(mesh: Mesh | None = None) -> FastAPI:
    engine = mesh or Mesh(default_db_path())
    if mesh is None:
        _ensure_demo_archive(engine)
    app = FastAPI(title="Mind Shared", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "product": "mind-shared"}

    @app.get("/workspaces")
    def list_workspaces() -> list[dict[str, str]]:
        return engine.workspaces.list()

    @app.post("/workspaces")
    def create_workspace(body: WorkspaceIn) -> dict[str, str]:
        return engine.workspaces.create(body.slug, body.name)

    @app.get("/workspaces/{workspace_id}/documents")
    def list_documents(workspace_id: str) -> list[dict[str, str | int]]:
        return engine.documents(workspace_id)

    @app.get("/workspaces/{workspace_id}/graph")
    def graph(workspace_id: str) -> dict[str, list[dict[str, str]]]:
        return engine.graph_snapshot(workspace_id)

    @app.post("/workspaces/{workspace_id}/ingest")
    async def ingest(workspace_id: str, file: UploadFile = File(...)) -> dict[str, str | int]:
        data = await file.read()
        try:
            return engine.ingest_upload(workspace_id, file.filename or "arquivo.txt", data)
        except UnsupportedFormatError as exc:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="formato não suportado",
            ) from exc

    @app.post("/workspaces/{workspace_id}/seed")
    def seed(workspace_id: str) -> dict[str, object]:
        ingested = engine.ingest_corpus(workspace_id, corpus_dir())
        return {"ingested": ingested}

    @app.post("/workspaces/{workspace_id}/query")
    def query(workspace_id: str, body: QueryIn) -> dict[str, object]:
        result = engine.query(workspace_id, body.question, hops=body.hops)
        return _query_payload(result)

    @app.post("/workspaces/{workspace_id}/feedback")
    def feedback(workspace_id: str, body: FeedbackIn) -> dict[str, str]:
        try:
            feedback_id = engine.mark_feedback(
                workspace_id, body.chunk_id, body.label, body.query_id
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="feedback inválido",
            ) from exc
        return {"feedback_id": feedback_id}

    @app.post("/workspaces/{workspace_id}/eval")
    def evaluate(workspace_id: str) -> dict[str, object]:
        gold = Path(__file__).resolve().parent.parent.parent / "eval" / "gold.json"
        return run_harness(engine, workspace_id, gold)

    return app
