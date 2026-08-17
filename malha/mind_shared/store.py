from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  title TEXT NOT NULL,
  source_path TEXT NOT NULL,
  mime TEXT NOT NULL,
  checksum TEXT NOT NULL,
  ingested_at TEXT NOT NULL,
  UNIQUE(workspace_id, checksum)
);

CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id),
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  ordinal INTEGER NOT NULL,
  text TEXT NOT NULL,
  start_char INTEGER NOT NULL,
  end_char INTEGER NOT NULL,
  embedding BLOB
);

CREATE TABLE IF NOT EXISTS terms (
  chunk_id TEXT NOT NULL REFERENCES chunks(id),
  term TEXT NOT NULL,
  tf INTEGER NOT NULL,
  PRIMARY KEY (chunk_id, term)
);

CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  canonical TEXT NOT NULL,
  UNIQUE(workspace_id, canonical)
);

CREATE TABLE IF NOT EXISTS relations (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  src_entity_id TEXT NOT NULL REFERENCES entities(id),
  dst_entity_id TEXT NOT NULL REFERENCES entities(id),
  predicate TEXT NOT NULL,
  evidence_chunk_id TEXT NOT NULL REFERENCES chunks(id)
);

CREATE TABLE IF NOT EXISTS entity_chunks (
  entity_id TEXT NOT NULL REFERENCES entities(id),
  chunk_id TEXT NOT NULL REFERENCES chunks(id),
  PRIMARY KEY (entity_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS queries (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  query_id TEXT REFERENCES queries(id),
  chunk_id TEXT NOT NULL REFERENCES chunks(id),
  label TEXT NOT NULL CHECK(label IN ('useful', 'wrong')),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_tokens (
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  token_hash TEXT NOT NULL,
  label TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (workspace_id, token_hash)
);

CREATE INDEX IF NOT EXISTS idx_chunks_ws ON chunks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term);
CREATE INDEX IF NOT EXISTS idx_entities_ws ON entities(workspace_id);
CREATE INDEX IF NOT EXISTS idx_entity_chunks_chunk ON entity_chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_feedback_chunk ON feedback(chunk_id);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        with self.connect() as con:
            con.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def conn(self) -> sqlite3.Connection:
        current = getattr(self._local, "conn", None)
        if current is None:
            current = self.connect()
            self._local.conn = current
        return current

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conn().execute(sql, tuple(params))

    def executemany(self, sql: str, seq: Iterable[Iterable[Any]]) -> sqlite3.Cursor:
        return self.conn().executemany(sql, list(seq))

    def commit(self) -> None:
        self.conn().commit()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()
