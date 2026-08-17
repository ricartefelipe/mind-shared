from __future__ import annotations

from mind_shared.ingest.parsers import stable_id
from mind_shared.store import Store, utcnow


class WorkspaceBook:
    def __init__(self, store: Store) -> None:
        self.store = store

    def create(self, slug: str, name: str) -> dict[str, str]:
        workspace_id = stable_id("ws", slug)
        self.store.execute(
            """
            INSERT INTO workspaces(id, slug, name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET name = excluded.name
            """,
            (workspace_id, slug, name, utcnow()),
        )
        self.store.commit()
        return self.get(workspace_id)

    def get(self, workspace_id: str) -> dict[str, str]:
        row = self.store.fetchone(
            "SELECT id, slug, name, created_at FROM workspaces WHERE id = ?",
            (workspace_id,),
        )
        if row is None:
            raise KeyError(workspace_id)
        return dict(row)

    def by_slug(self, slug: str) -> dict[str, str] | None:
        row = self.store.fetchone(
            "SELECT id, slug, name, created_at FROM workspaces WHERE slug = ?",
            (slug,),
        )
        return dict(row) if row else None

    def list(self) -> list[dict[str, str]]:
        return [
            dict(row)
            for row in self.store.fetchall(
                "SELECT id, slug, name, created_at FROM workspaces ORDER BY name"
            )
        ]
