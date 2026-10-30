from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

from mind_shared.config import SQLITE_BUSY_TIMEOUT_MS


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

# Colunas adicionadas depois da primeira versão do esquema. Bancos antigos recebem cada coluna
# uma vez (ALTER TABLE é idempotente aqui porque conferimos PRAGMA table_info antes).
MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("workspace_tokens", "id", "ALTER TABLE workspace_tokens ADD COLUMN id TEXT"),
    ("workspace_tokens", "role", "ALTER TABLE workspace_tokens ADD COLUMN role TEXT NOT NULL DEFAULT 'admin'"),
    ("workspace_tokens", "expires_at", "ALTER TABLE workspace_tokens ADD COLUMN expires_at TEXT"),
    ("workspace_tokens", "revoked_at", "ALTER TABLE workspace_tokens ADD COLUMN revoked_at TEXT"),
    ("workspace_tokens", "last_used_at", "ALTER TABLE workspace_tokens ADD COLUMN last_used_at TEXT"),
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path, busy_timeout_ms: int = SQLITE_BUSY_TIMEOUT_MS) -> None:
        self.path = path
        self.busy_timeout_ms = busy_timeout_ms
        path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        with self.connect() as con:
            con.executescript(SCHEMA)
            self._migrate(con)

    @staticmethod
    def _migrate(con: sqlite3.Connection) -> None:
        for table, column, ddl in MIGRATIONS:
            present = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            if column not in present:
                con.execute(ddl)
        con.commit()

    def connect(self) -> sqlite3.Connection:
        # WAL (no esquema) permite leituras durante uma escrita; busy_timeout faz escritores
        # concorrentes esperarem em vez de falhar com "database is locked".
        con = sqlite3.connect(self.path, check_same_thread=False, timeout=self.busy_timeout_ms / 1000)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
        return con

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Escrita atômica: tudo ou nada, com rollback em qualquer exceção."""
        con = self.conn()
        con.execute("BEGIN IMMEDIATE")
        try:
            yield con
        except BaseException:
            con.rollback()
            raise
        else:
            con.commit()

    def backup(self, destination: Path) -> Path:
        """Cópia consistente do banco (API de backup do SQLite, válida com WAL e com escritores ativos)."""
        destination = self._backup_destination(destination)
        with sqlite3.connect(str(destination)) as target:
            self.conn().backup(target)
        return destination

    def _backup_destination(self, raw: Path) -> Path:
        """Destino explícito do operador: caminho absoluto resolvido, extensão .sqlite, em diretório já
        existente, nunca o próprio banco (nem seus arquivos WAL/SHM) e nunca um arquivo existente."""
        destination = Path(raw).expanduser().resolve()
        live = self.path.resolve()
        if destination.suffix != ".sqlite":
            raise ValueError("o destino do backup deve terminar em .sqlite")
        if destination == live or destination.parent == live.parent and destination.name.startswith(live.name):
            raise ValueError("o destino do backup não pode ser o banco em uso")
        if not destination.parent.is_dir():
            raise ValueError(f"diretório do backup não existe: {destination.parent}")
        if destination.exists():
            raise FileExistsError(destination)
        return destination

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
