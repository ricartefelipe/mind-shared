from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from mind_shared.config import GRAPH_HOPS_DEFAULT
from mind_shared.graph.extract import GraphIndex
from mind_shared.index.dense import DenseIndex
from mind_shared.index.embeddings import EmbeddingBackend, load_backend
from mind_shared.index.sparse import SparseIndex
from mind_shared.ingest.chunking import chunk_text
from mind_shared.ingest.parsers import (
    UnsupportedFormatError,
    document_checksum,
    parse_bytes,
    parse_path,
    stable_id,
)
from mind_shared.memory.feedback import FeedbackMemory
from mind_shared.memory.workspaces import WorkspaceBook
from mind_shared.retrieve.pipeline import Retriever
from mind_shared.store import Store, utcnow
from mind_shared.synthesize.grounded import synthesize
from mind_shared.types import FeedbackLabel, ParsedDocument, QueryResult


class Mesh:
    def __init__(self, db_path: Path, embedding: EmbeddingBackend | None = None) -> None:
        self.store = Store(db_path)
        self.embedding = embedding or load_backend("hash")
        self.workspaces = WorkspaceBook(self.store)
        self.sparse = SparseIndex(self.store)
        self.dense = DenseIndex(self.store, self.embedding)
        self.graph = GraphIndex(self.store)
        self.feedback = FeedbackMemory(self.store)
        self.retriever = Retriever(
            self.store, self.sparse, self.dense, self.graph, self.feedback
        )

    def ingest_path(self, workspace_id: str, path: Path) -> dict[str, str | int]:
        parsed = parse_path(path)
        return self._ingest_parsed(workspace_id, parsed)

    def ingest_upload(
        self, workspace_id: str, filename: str, data: bytes
    ) -> dict[str, str | int]:
        parsed = parse_bytes(filename, data)
        return self._ingest_parsed(workspace_id, parsed)

    def ingest_corpus(self, workspace_id: str, corpus: Path) -> list[dict[str, str | int]]:
        ingested: list[dict[str, str | int]] = []
        for path in sorted(corpus.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {
                ".md",
                ".markdown",
                ".txt",
                ".pdf",
            }:
                continue
            ingested.append(self.ingest_path(workspace_id, path))
        return ingested

    def query(
        self,
        workspace_id: str,
        question: str,
        hops: int = GRAPH_HOPS_DEFAULT,
    ) -> QueryResult:
        evidence = self.retriever.search(workspace_id, question, hops=hops)
        answer = synthesize(question, evidence)
        query_id = uuid4().hex
        self.store.execute(
            "INSERT INTO queries(id, workspace_id, text, created_at) VALUES (?, ?, ?, ?)",
            (query_id, workspace_id, question, utcnow()),
        )
        self.store.commit()
        return QueryResult(
            query_id=query_id,
            question=question,
            answer=answer,
            evidence=evidence,
        )

    def mark_feedback(
        self,
        workspace_id: str,
        chunk_id: str,
        label: FeedbackLabel,
        query_id: str | None = None,
    ) -> str:
        return self.feedback.record(workspace_id, chunk_id, label, query_id)

    def documents(self, workspace_id: str) -> list[dict[str, str | int]]:
        rows = self.store.fetchall(
            """
            SELECT d.id, d.title, d.source_path, d.mime, d.ingested_at,
                   COUNT(c.id) AS chunks
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.id
            WHERE d.workspace_id = ?
            GROUP BY d.id
            ORDER BY d.ingested_at DESC
            """,
            (workspace_id,),
        )
        return [dict(row) for row in rows]

    def graph_snapshot(self, workspace_id: str) -> dict[str, list[dict[str, str]]]:
        return self.graph.snapshot(workspace_id)

    def _ingest_parsed(
        self, workspace_id: str, parsed: ParsedDocument
    ) -> dict[str, str | int]:
        checksum = document_checksum(parsed)
        existing = self.store.fetchone(
            "SELECT id FROM documents WHERE workspace_id = ? AND checksum = ?",
            (workspace_id, checksum),
        )
        if existing:
            return {"document_id": existing["id"], "title": parsed.title, "chunks": 0, "status": "duplicate"}
        document_id = stable_id(workspace_id, checksum)
        self.store.execute(
            """
            INSERT INTO documents(id, workspace_id, title, source_path, mime, checksum, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                workspace_id,
                parsed.title,
                parsed.source_path,
                parsed.mime,
                checksum,
                utcnow(),
            ),
        )
        drafts = chunk_text(parsed.text)
        for draft in drafts:
            chunk_id = stable_id(document_id, str(draft.ordinal), draft.text[:40])
            embedding = self.dense.encode(draft.text)
            self.store.execute(
                """
                INSERT INTO chunks(
                  id, document_id, workspace_id, ordinal, text, start_char, end_char, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    document_id,
                    workspace_id,
                    draft.ordinal,
                    draft.text,
                    draft.start_char,
                    draft.end_char,
                    embedding,
                ),
            )
            self.sparse.index_chunk(chunk_id, draft.text)
            self.graph.ingest_chunk(workspace_id, chunk_id, draft.text)
        self.store.commit()
        return {
            "document_id": document_id,
            "title": parsed.title,
            "chunks": len(drafts),
            "status": "ingested",
        }


__all__ = ["Mesh", "UnsupportedFormatError"]
