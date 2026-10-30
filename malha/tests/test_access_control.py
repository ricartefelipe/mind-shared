from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mind_shared.api.app import create_app
from mind_shared.auth.tokens import Role, TokenBook
from mind_shared.config import DEMO_TOKEN
from mind_shared.engine import Mesh
from mind_shared.index.embeddings import HashingTrickEmbedding
from mind_shared.synthesize.composer import ExtractiveComposer


def headers(token: str) -> dict[str, str]:
    return {"X-Mind-Token": token}


def new_mesh(tmp_path: Path, name: str = "mesh.sqlite") -> Mesh:
    return Mesh(tmp_path / name, embedding=HashingTrickEmbedding(), composer=ExtractiveComposer())


def test_demo_token_is_issued_only_for_demo_workspace_in_local_profile(mesh, monkeypatch) -> None:
    monkeypatch.delenv("MIND_PROFILE", raising=False)
    demo = mesh.provision_workspace("atlas-norte", "Arquivo Atlas Norte")
    other = mesh.provision_workspace("outro", "Outro espaço")
    assert demo["token"] == DEMO_TOKEN
    assert other["token"] != DEMO_TOKEN
    # Conhecer o slug/id de outro espaço não concede acesso: o token é verificado contra o espaço da URL.
    assert mesh.tokens.authenticate(other["id"], DEMO_TOKEN) is None
    assert mesh.tokens.authenticate(demo["id"], other["token"]) is None


def test_demo_token_is_refused_in_remote_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MIND_PROFILE", "remote")
    monkeypatch.setenv("MIND_ADMIN_TOKEN", "admin-secret-for-tests")
    mesh = new_mesh(tmp_path)
    created = mesh.provision_workspace("atlas-norte", "Arquivo Atlas Norte")
    assert created["token"] != DEMO_TOKEN
    assert mesh.tokens.authenticate(created["id"], DEMO_TOKEN) is None
    with pytest.raises(PermissionError):
        mesh.tokens.issue(created["id"], "atlas-norte", token=DEMO_TOKEN)

    client = TestClient(create_app(mesh))
    # Seed e espaço de demonstração não existem no perfil remoto.
    assert client.post(f"/workspaces/{created['id']}/seed", headers=headers(created["token"])).status_code == 404
    assert client.post("/workspaces", json={"slug": "novo", "name": "Novo"}).status_code == 401
    assert client.post("/workspaces", json={"slug": "novo", "name": "Novo"}, headers={"X-Mind-Admin-Token": "errado"}).status_code == 401
    ok = client.post("/workspaces", json={"slug": "novo", "name": "Novo"}, headers={"X-Mind-Admin-Token": "admin-secret-for-tests"})
    assert ok.status_code == 200
    assert client.post("/workspaces", json={"slug": "atlas-norte", "name": "Demo"}, headers={"X-Mind-Admin-Token": "admin-secret-for-tests"}).status_code == 403


def test_remote_profile_requires_admin_token_to_start(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MIND_PROFILE", "remote")
    monkeypatch.delenv("MIND_ADMIN_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        create_app(new_mesh(tmp_path))


def test_roles_limit_each_route(atlas) -> None:
    mesh, workspace_id = atlas
    client = TestClient(create_app(mesh))
    admin = mesh.tokens.list(workspace_id)
    admin_token = DEMO_TOKEN
    reader = client.post(f"/workspaces/{workspace_id}/tokens", json={"role": "reader", "label": "leitor"}, headers=headers(admin_token))
    editor = client.post(f"/workspaces/{workspace_id}/tokens", json={"role": "editor", "label": "editor"}, headers=headers(admin_token))
    assert reader.status_code == 201 and editor.status_code == 201
    reader_token = reader.json()["token"]
    editor_token = editor.json()["token"]
    documents = client.get(f"/workspaces/{workspace_id}/documents", headers=headers(reader_token)).json()

    # leitor consulta e lê, mas não ingere, não dá feedback, não exclui nem gere tokens
    assert client.post(f"/workspaces/{workspace_id}/query", json={"question": "Quem acessa produção?"}, headers=headers(reader_token)).status_code == 200
    assert client.post(f"/workspaces/{workspace_id}/feedback", json={"chunk_id": "x", "label": "useful"}, headers=headers(reader_token)).status_code == 403
    assert client.delete(f"/workspaces/{workspace_id}/documents/{documents[0]['id']}", headers=headers(reader_token)).status_code == 403
    assert client.get(f"/workspaces/{workspace_id}/tokens", headers=headers(reader_token)).status_code == 403
    assert client.post(f"/workspaces/{workspace_id}/tokens", json={"role": "admin"}, headers=headers(reader_token)).status_code == 403
    # editor ingere e exclui, mas não gere tokens
    assert client.get(f"/workspaces/{workspace_id}/tokens", headers=headers(editor_token)).status_code == 403
    assert client.delete(f"/workspaces/{workspace_id}/documents/{documents[0]['id']}", headers=headers(editor_token)).status_code == 204
    assert len(admin) >= 1


def test_revoked_and_expired_tokens_stop_working(atlas) -> None:
    mesh, workspace_id = atlas
    client = TestClient(create_app(mesh))
    issued = mesh.tokens.issue(workspace_id, "atlas-norte", role=Role.READER, label="temporário", ttl_days=1)
    assert client.get(f"/workspaces/{workspace_id}/documents", headers=headers(issued.token)).status_code == 200

    assert client.delete(f"/workspaces/{workspace_id}/tokens/{issued.id}", headers=headers(DEMO_TOKEN)).status_code == 204
    assert client.get(f"/workspaces/{workspace_id}/documents", headers=headers(issued.token)).status_code == 401
    assert client.delete(f"/workspaces/{workspace_id}/tokens/{issued.id}", headers=headers(DEMO_TOKEN)).status_code == 404

    expired = mesh.tokens.issue(workspace_id, "atlas-norte", role=Role.READER, label="vencido", ttl_days=1)
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds")
    mesh.store.execute("UPDATE workspace_tokens SET expires_at = ? WHERE id = ?", (past, expired.id))
    mesh.store.commit()
    assert client.get(f"/workspaces/{workspace_id}/documents", headers=headers(expired.token)).status_code == 401
    listed = {t["id"]: t for t in client.get(f"/workspaces/{workspace_id}/tokens", headers=headers(DEMO_TOKEN)).json()}
    assert listed[issued.id]["revoked_at"] is not None
    assert "token" not in listed[issued.id]  # só hash no banco; o token nunca volta na listagem


def test_old_database_without_token_columns_is_migrated(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "antigo.sqlite"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE workspaces (id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE workspace_tokens (workspace_id TEXT NOT NULL REFERENCES workspaces(id), token_hash TEXT NOT NULL, label TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, token_hash));
        INSERT INTO workspaces VALUES ('ws1','legado','Legado','2026-01-01T00:00:00+00:00');
        """
    )
    from mind_shared.auth.tokens import hash_token

    con.execute("INSERT INTO workspace_tokens VALUES ('ws1', ?, 'legado', '2026-01-01T00:00:00+00:00')", (hash_token("token-antigo"),))
    con.commit()
    con.close()

    mesh = new_mesh(tmp_path, "antigo.sqlite")
    principal = mesh.tokens.authenticate("ws1", "token-antigo")
    assert principal is not None and principal.role is Role.ADMIN  # token anterior continua válido, como administrador
    assert mesh.tokens.list("ws1")[0]["expires_at"] is None
