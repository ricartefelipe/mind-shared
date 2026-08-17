from __future__ import annotations

import hashlib
import secrets

from mind_shared.config import DEMO_TOKEN, DEMO_WORKSPACE_SLUG
from mind_shared.store import Store, utcnow


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenBook:
    def __init__(self, store: Store) -> None:
        self.store = store

    def issue(self, workspace_id: str, slug: str, token: str | None = None) -> str:
        if slug == DEMO_WORKSPACE_SLUG:
            raw = token or DEMO_TOKEN
        else:
            raw = token or secrets.token_urlsafe(24)
        digest = hash_token(raw)
        existing = self.store.fetchone(
            "SELECT token_hash FROM workspace_tokens WHERE workspace_id = ? AND token_hash = ?",
            (workspace_id, digest),
        )
        if existing is None:
            self.store.execute(
                """
                INSERT INTO workspace_tokens(workspace_id, token_hash, label, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (workspace_id, digest, slug, utcnow()),
            )
            self.store.commit()
        return raw

    def verify(self, workspace_id: str, token: str | None) -> bool:
        if not token:
            return False
        row = self.store.fetchone(
            "SELECT token_hash FROM workspace_tokens WHERE workspace_id = ? AND token_hash = ?",
            (workspace_id, hash_token(token)),
        )
        return row is not None
