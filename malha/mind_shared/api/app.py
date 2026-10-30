from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Header, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from mind_shared.api.schemas import (
    TokenIn,
    TokenOut,
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
from mind_shared.config import (
    DEMO_WORKSPACE_SLUG,
    admin_token,
    composer_backend,
    composer_gguf_path,
    composer_model,
    composer_url,
    corpus_dir,
    default_db_path,
    demo_allowed,
    embedding_backend_name,
    embedding_model_name,
    is_remote,
)
from mind_shared.auth.tokens import Role
from mind_shared.engine import Mesh
from mind_shared.eval.harness import run_harness
from mind_shared.ingest.parsers import UnsupportedFormatError
from mind_shared.types import FeedbackLabel


def _ensure_demo_archive(engine: Mesh) -> None:
    """Espaço de demonstração com o corpus de exemplo: só no perfil local."""
    if not demo_allowed() or engine.workspaces.list():
        return
    workspace = engine.provision_workspace(DEMO_WORKSPACE_SLUG, "Arquivo Atlas Norte")
    engine.ingest_corpus(workspace["id"], corpus_dir())


def _require_admin_configured() -> None:
    if is_remote() and admin_token() is None:
        raise RuntimeError("MIND_PROFILE=remote exige MIND_ADMIN_TOKEN para criar espaços")


def create_app(mesh: Mesh | None = None) -> FastAPI:
    _require_admin_configured()
    engine = mesh or Mesh(default_db_path())
    if mesh is None:
        _ensure_demo_archive(engine)
    app = FastAPI(title="Mind Shared", version="0.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _workspace(ref: str) -> str:
        try:
            return engine.workspaces.resolve(ref)["id"]
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="espaço não encontrado",
            ) from exc

    def _authorize(workspace_ref: str, token: str | None, required: Role = Role.READER) -> str:
        """Token do próprio espaço (não revogado, não expirado) com papel suficiente.
        Conhecer o id ou o slug de outro espaço não dá acesso: o token é verificado contra
        o espaço da URL."""
        workspace_id = _workspace(workspace_ref)
        principal = engine.tokens.authenticate(workspace_id, token)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="token ausente ou inválido",
            )
        if not principal.role.allows(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"papel {principal.role.value} não permite esta operação (exige {required.value})",
            )
        return workspace_id

    def _authorize_install_admin(token: str | None) -> None:
        """Criação de espaços: no perfil remoto exige o token de administração da instalação."""
        expected = admin_token()
        if expected is None:
            if is_remote():
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="administração não configurada")
            return
        if not token or not secrets.compare_digest(token, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token de administração inválido")

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "status": "ok",
            "product": "mind-shared",
            "health": "/health",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    @app.get("/health")
    def health() -> dict[str, str | None]:
        embedding = type(engine.embedding).__name__
        llm_url = composer_url()
        backend = composer_backend()
        return {
            "status": "ok",
            "product": "mind-shared",
            "composer": engine.composer.name,
            "composer_backend": backend or None,
            "composer_model": composer_model() if llm_url else None,
            "composer_url": llm_url or None,
            "composer_gguf": str(composer_gguf_path()) if backend == "local" else None,
            "embedding": embedding,
            "embedding_model": embedding_model_name() or None,
            "embedding_backend": embedding_backend_name() or None,
        }

    @app.get("/workspaces")
    def list_workspaces() -> list[dict[str, str]]:
        return engine.workspaces.list()

    @app.post("/workspaces")
    def create_workspace(
        body: WorkspaceIn,
        x_mind_admin_token: Annotated[str | None, Header()] = None,
    ) -> WorkspaceOut:
        _authorize_install_admin(x_mind_admin_token)
        if body.slug == DEMO_WORKSPACE_SLUG and not demo_allowed():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="espaço de demonstração indisponível neste perfil")
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
        workspace_id = _authorize(workspace_id, x_mind_token)
        return engine.documents(workspace_id)

    @app.get("/workspaces/{workspace_id}/graph")
    def graph(
        workspace_id: str,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> GraphOut:
        workspace_id = _authorize(workspace_id, x_mind_token)
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
        workspace_id = _authorize(workspace_id, x_mind_token)
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
        if not demo_allowed():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="seed indisponível neste perfil")
        workspace_id = _authorize(workspace_id, x_mind_token, Role.EDITOR)
        ingested = engine.ingest_corpus(workspace_id, corpus_dir())
        return {"ingested": ingested}

    @app.post("/workspaces/{workspace_id}/query")
    def query(
        workspace_id: str,
        body: QueryIn,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> QueryOut:
        workspace_id = _authorize(workspace_id, x_mind_token)
        result = engine.query(workspace_id, body.question, hops=body.hops)
        return query_out(result)

    @app.post("/v1/ask")
    def ask(
        body: AskIn,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> QueryOut:
        workspace_id = _authorize(body.workspace_id, x_mind_token)
        result = engine.query(workspace_id, body.question, hops=body.hops)
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
        workspace_id = _authorize(workspace_id, x_mind_token, Role.EDITOR)
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

    @app.delete(
        "/workspaces/{workspace_id}/documents/{document_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
    )
    def delete_document(
        workspace_id: str,
        document_id: str,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> Response:
        workspace_id = _authorize(workspace_id, x_mind_token, Role.EDITOR)
        try:
            engine.delete_document(workspace_id, document_id)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="documento não encontrado") from None
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/workspaces/{workspace_id}/tokens")
    def list_tokens(
        workspace_id: str,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> list[dict[str, str | None]]:
        workspace_id = _authorize(workspace_id, x_mind_token, Role.ADMIN)
        return engine.tokens.list(workspace_id)

    @app.post("/workspaces/{workspace_id}/tokens", status_code=status.HTTP_201_CREATED)
    def create_token(
        workspace_id: str,
        body: TokenIn,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> TokenOut:
        workspace_id = _authorize(workspace_id, x_mind_token, Role.ADMIN)
        workspace = engine.workspaces.get(workspace_id)
        issued = engine.tokens.issue(
            workspace_id, workspace["slug"], role=Role(body.role), label=body.label, ttl_days=body.ttl_days
        )
        return TokenOut(id=issued.id, token=issued.token, role=issued.role.value, label=issued.label, expires_at=issued.expires_at)

    @app.delete(
        "/workspaces/{workspace_id}/tokens/{token_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
    )
    def revoke_token(
        workspace_id: str,
        token_id: str,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> Response:
        workspace_id = _authorize(workspace_id, x_mind_token, Role.ADMIN)
        if not engine.tokens.revoke(workspace_id, token_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="token não encontrado")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/workspaces/{workspace_id}/eval")
    def evaluate(
        workspace_id: str,
        x_mind_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, object]:
        workspace_id = _authorize(workspace_id, x_mind_token)
        gold = Path(__file__).resolve().parent.parent.parent / "eval" / "gold.json"
        return run_harness(engine, workspace_id, gold)

    return app
