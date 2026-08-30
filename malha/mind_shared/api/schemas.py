from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from mind_shared.config import GRAPH_HOPS_DEFAULT
from mind_shared.types import (
    Contradiction,
    Evidence,
    GroundedAnswer,
    PlanStep,
    QueryResult,
    Verification,
)


class WorkspaceIn(BaseModel):
    slug: str
    name: str


class WorkspaceOut(BaseModel):
    id: str
    slug: str
    name: str
    created_at: str
    token: str | None = None


class QueryIn(BaseModel):
    question: str
    hops: int = Field(default=GRAPH_HOPS_DEFAULT, ge=0, le=3)


class AskIn(BaseModel):
    workspace_id: str
    question: str
    hops: int = Field(default=GRAPH_HOPS_DEFAULT, ge=0, le=3)


class FeedbackIn(BaseModel):
    chunk_id: str
    label: Literal["useful", "wrong"]
    query_id: str | None = None


class PlanStepOut(BaseModel):
    id: str
    objective: str
    kind: Literal["lookup", "hop", "compare"]


class ContradictionOut(BaseModel):
    left_chunk_id: str
    right_chunk_id: str
    subject: str
    left_claim: str
    right_claim: str
    reason: str


class VerificationOut(BaseModel):
    status: Literal["grounded", "conflict", "insufficient"]
    coverage: float
    contradictions: list[ContradictionOut]
    notes: list[str]


class AnswerOut(BaseModel):
    text: str
    refused: bool
    refusal_reason: str | None
    cited_chunk_ids: list[str]
    grounding_status: Literal["grounded", "conflict", "insufficient"]


class EvidenceOut(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    source_path: str
    excerpt: str
    score: float
    hop: int
    entity_path: list[str]
    start_char: int
    end_char: int
    ordinal: int


class QueryOut(BaseModel):
    query_id: str
    question: str
    answer: AnswerOut
    evidence: list[EvidenceOut]
    plan: list[PlanStepOut]
    verification: VerificationOut
    composer: Literal["extractive", "http", "local"]


class GraphConflictOut(BaseModel):
    left_chunk_id: str
    right_chunk_id: str
    subject: str
    left_claim: str
    right_claim: str
    reason: str


class GraphOut(BaseModel):
    entities: list[dict[str, str]]
    relations: list[dict[str, str]]
    conflicts: list[GraphConflictOut]


def evidence_out(item: Evidence) -> EvidenceOut:
    return EvidenceOut(
        chunk_id=item.chunk_id,
        document_id=item.document_id,
        document_title=item.document_title,
        source_path=item.source_path,
        excerpt=item.excerpt,
        score=item.score,
        hop=item.hop,
        entity_path=list(item.entity_path),
        start_char=item.start_char,
        end_char=item.end_char,
        ordinal=item.ordinal,
    )


def plan_out(step: PlanStep) -> PlanStepOut:
    return PlanStepOut(id=step.id, objective=step.objective, kind=step.kind)


def contradiction_out(item: Contradiction) -> ContradictionOut:
    return ContradictionOut(
        left_chunk_id=item.left_chunk_id,
        right_chunk_id=item.right_chunk_id,
        subject=item.subject,
        left_claim=item.left_claim,
        right_claim=item.right_claim,
        reason=item.reason,
    )


def verification_out(item: Verification | None) -> VerificationOut:
    if item is None:
        return VerificationOut(
            status="insufficient",
            coverage=0.0,
            contradictions=[],
            notes=[],
        )
    return VerificationOut(
        status=item.status.value,
        coverage=item.coverage,
        contradictions=[contradiction_out(row) for row in item.contradictions],
        notes=list(item.notes),
    )


def answer_out(item: GroundedAnswer) -> AnswerOut:
    return AnswerOut(
        text=item.text,
        refused=item.refused,
        refusal_reason=item.refusal_reason,
        cited_chunk_ids=list(item.cited_chunk_ids),
        grounding_status=item.grounding_status.value,
    )


def query_out(result: QueryResult) -> QueryOut:
    return QueryOut(
        query_id=result.query_id,
        question=result.question,
        answer=answer_out(result.answer),
        evidence=[evidence_out(item) for item in result.evidence],
        plan=[plan_out(step) for step in result.plan],
        verification=verification_out(result.verification),
        composer=result.composer,
    )
