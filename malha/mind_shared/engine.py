from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from mind_shared.auth.tokens import TokenBook
from mind_shared.config import GRAPH_HOPS_DEFAULT
from mind_shared.graph.conflicts import graph_conflicts
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
from mind_shared.plan.decompose import decompose
from mind_shared.retrieve.pipeline import Retriever
from mind_shared.store import Store, utcnow
from mind_shared.synthesize.composer import Composer, load_composer
from mind_shared.types import (
    ComposerName,
    Contradiction,
    FeedbackLabel,
    ParsedDocument,
    QueryResult,
)
from mind_shared.verify.engine import verify


class Mesh:
    def __init__(
        self,
        db_path: Path,
        embedding: EmbeddingBackend | None = None,
        composer: Composer | None = None,
    ) -> None:
        self.store = Store(db_path)
        self.embedding = embedding or load_backend()
        self.composer: Composer = composer or load_composer()
        self.workspaces = WorkspaceBook(self.store)
        self.tokens = TokenBook(self.store)
        self.sparse = SparseIndex(self.store)
        self.dense = DenseIndex(self.store, self.embedding)
        self.graph = GraphIndex(self.store)
        self.feedback = FeedbackMemory(self.store)
        self.retriever = Retriever(
            self.store, self.sparse, self.dense, self.graph, self.feedback
        )

    def provision_workspace(self, slug: str, name: str) -> dict[str, str]:
        workspace = self.workspaces.create(slug, name)
        token = self.tokens.issue(workspace["id"], slug)
        return {**workspace, "token": token}

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
        plan = decompose(question)
        evidence = self.retriever.search_subgoals(
            workspace_id,
            tuple(step.objective for step in plan),
            hops=hops,
        )
        graph_hits = graph_conflicts(self.graph, workspace_id)
        scoped = _scope_conflicts(graph_hits, evidence)
        verification = verify(question, evidence, scoped)
        answer = self.composer.compose(question, evidence, verification)
        query_id = uuid4().hex
        self.store.execute(
            "INSERT INTO queries(id, workspace_id, text, created_at) VALUES (?, ?, ?, ?)",
            (query_id, workspace_id, question, utcnow()),
        )
        self.store.commit()
        composer_name: ComposerName = self.composer.name
        return QueryResult(
            query_id=query_id,
            question=question,
            answer=answer,
            evidence=evidence,
            plan=plan,
            verification=verification,
            composer=composer_name,
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
        snap = self.graph.snapshot(workspace_id)
        snap["conflicts"] = [
            {
                "left_chunk_id": item.left_chunk_id,
                "right_chunk_id": item.right_chunk_id,
                "subject": item.subject,
                "left_claim": item.left_claim,
                "right_claim": item.right_claim,
                "reason": item.reason,
            }
            for item in graph_conflicts(self.graph, workspace_id)
        ]
        return snap

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


def _scope_conflicts(
    hits: tuple[Contradiction, ...], evidence: list
) -> tuple[Contradiction, ...]:
    known = {item.chunk_id for item in evidence}
    if not known:
        return ()
    scoped = [
        item
        for item in hits
        if item.left_chunk_id in known or item.right_chunk_id in known
    ]
    return tuple(scoped)


__all__ = ["Mesh", "UnsupportedFormatError"]
