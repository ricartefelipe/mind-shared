from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import uuid4

from mind_shared.config import (
    DEFAULT_TOKEN_TTL_DAYS,
    DEMO_TOKEN,
    DEMO_WORKSPACE_SLUG,
    demo_allowed,
)
from mind_shared.store import Store, utcnow


class Role(str, Enum):
    """Papéis por espaço. Um papel mais alto inclui os mais baixos."""

    READER = "reader"
    EDITOR = "editor"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        return {Role.READER: 1, Role.EDITOR: 2, Role.ADMIN: 3}[self]

    def allows(self, required: "Role") -> bool:
        return self.rank >= required.rank


@dataclass(frozen=True)
class Principal:
    """Quem está autenticado: um token válido de um espaço, com papel."""

    workspace_id: str
    token_id: str
    role: Role
    label: str


@dataclass(frozen=True)
class IssuedToken:
    id: str
    token: str
    role: Role
    label: str
    expires_at: str | None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TokenBook:
    """Credenciais por espaço: hash no banco, papel, expiração e revogação.

    O token de demonstração só existe no perfil local e só para o espaço de demonstração;
    num perfil remoto ele nunca é emitido nem aceito."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def issue(
        self,
        workspace_id: str,
        slug: str,
        token: str | None = None,
        *,
        role: Role = Role.ADMIN,
        label: str | None = None,
        ttl_days: int | None = DEFAULT_TOKEN_TTL_DAYS,
        demo: bool = False,
    ) -> IssuedToken:
        """`demo=True` só no provisionamento do espaço de demonstração: devolve a credencial
        fixa documentada, se o perfil permitir. Qualquer outro token é aleatório."""
        if demo and slug == DEMO_WORKSPACE_SLUG and token is None and demo_allowed():
            raw = DEMO_TOKEN
        else:
            raw = token or secrets.token_urlsafe(24)
        if raw == DEMO_TOKEN and not demo_allowed():
            raise PermissionError("credencial de demonstração não é permitida neste perfil")
        digest = hash_token(raw)
        expires_at = (
            (_now() + timedelta(days=ttl_days)).isoformat(timespec="seconds") if ttl_days else None
        )
        existing = self.store.fetchone(
            "SELECT id, role, label, expires_at FROM workspace_tokens WHERE workspace_id = ? AND token_hash = ?",
            (workspace_id, digest),
        )
        if existing is not None:
            return IssuedToken(
                existing["id"] or "", raw, Role(existing["role"]), existing["label"], existing["expires_at"]
            )
        token_id = uuid4().hex
        self.store.execute(
            """
            INSERT INTO workspace_tokens(id, workspace_id, token_hash, label, role, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (token_id, workspace_id, digest, label or slug, role.value, utcnow(), expires_at),
        )
        self.store.commit()
        return IssuedToken(token_id, raw, role, label or slug, expires_at)

    def authenticate(self, workspace_id: str, token: str | None) -> Principal | None:
        """Devolve o principal se o token for deste espaço, não revogado e não expirado."""
        if not token:
            return None
        if token == DEMO_TOKEN and not demo_allowed():
            return None
        row = self.store.fetchone(
            """
            SELECT id, role, label, expires_at, revoked_at
            FROM workspace_tokens WHERE workspace_id = ? AND token_hash = ?
            """,
            (workspace_id, hash_token(token)),
        )
        if row is None or row["revoked_at"] is not None:
            return None
        if row["expires_at"] is not None and datetime.fromisoformat(row["expires_at"]) <= _now():
            return None
        self.store.execute(
            "UPDATE workspace_tokens SET last_used_at = ? WHERE workspace_id = ? AND token_hash = ?",
            (utcnow(), workspace_id, hash_token(token)),
        )
        self.store.commit()
        return Principal(workspace_id, row["id"] or "", Role(row["role"]), row["label"])

    def verify(self, workspace_id: str, token: str | None) -> bool:
        return self.authenticate(workspace_id, token) is not None

    def revoke(self, workspace_id: str, token_id: str) -> bool:
        cursor = self.store.execute(
            "UPDATE workspace_tokens SET revoked_at = ? WHERE workspace_id = ? AND id = ? AND revoked_at IS NULL",
            (utcnow(), workspace_id, token_id),
        )
        self.store.commit()
        return cursor.rowcount == 1

    def list(self, workspace_id: str) -> list[dict[str, str | None]]:
        rows = self.store.fetchall(
            """
            SELECT id, label, role, created_at, expires_at, revoked_at, last_used_at
            FROM workspace_tokens WHERE workspace_id = ? ORDER BY created_at
            """,
            (workspace_id,),
        )
        return [dict(row) for row in rows]
