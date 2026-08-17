from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Never

PlanKind = Literal["lookup", "hop", "compare"]
ComposerName = Literal["extractive", "http"]


class EntityType(str, Enum):
    PERSON = "person"
    ORG = "org"
    POLICY = "policy"
    DECISION = "decision"
    INCIDENT = "incident"
    SYSTEM = "system"
    CONCEPT = "concept"
    SPACE = "space"


class FeedbackLabel(str, Enum):
    USEFUL = "useful"
    WRONG = "wrong"


class GroundingStatus(str, Enum):
    GROUNDED = "grounded"
    CONFLICT = "conflict"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    text: str
    mime: str
    source_path: str


@dataclass(frozen=True)
class ChunkDraft:
    ordinal: int
    text: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class RankedHit:
    chunk_id: str
    score: float
    channel: Literal["dense", "sparse", "graph", "fused"]
    hop: int = 0
    entity_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    document_id: str
    document_title: str
    source_path: str
    excerpt: str
    score: float
    hop: int
    entity_path: tuple[str, ...]
    start_char: int
    end_char: int
    ordinal: int


@dataclass(frozen=True)
class PlanStep:
    id: str
    objective: str
    kind: PlanKind


@dataclass(frozen=True)
class Contradiction:
    left_chunk_id: str
    right_chunk_id: str
    subject: str
    left_claim: str
    right_claim: str
    reason: str


@dataclass(frozen=True)
class Verification:
    status: GroundingStatus
    coverage: float
    contradictions: tuple[Contradiction, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundedAnswer:
    text: str
    refused: bool
    refusal_reason: str | None
    cited_chunk_ids: tuple[str, ...]
    grounding_status: GroundingStatus = GroundingStatus.INSUFFICIENT


@dataclass
class QueryResult:
    query_id: str
    question: str
    answer: GroundedAnswer
    evidence: list[Evidence] = field(default_factory=list)
    plan: tuple[PlanStep, ...] = ()
    verification: Verification | None = None
    composer: ComposerName = "extractive"


@dataclass(frozen=True)
class EntityHit:
    entity_id: str
    name: str
    type: str
    canonical: str


@dataclass(frozen=True)
class RelationHit:
    relation_id: str
    src_name: str
    dst_name: str
    predicate: str
    evidence_chunk_id: str


def exhaust_grounding_status(value: GroundingStatus) -> str:
    match value:
        case GroundingStatus.GROUNDED:
            return "fundamentado"
        case GroundingStatus.CONFLICT:
            return "conflito"
        case GroundingStatus.INSUFFICIENT:
            return "insuficiente"
        case _ as unreachable:
            return _assert_never(unreachable)


def exhaust_plan_kind(value: PlanKind) -> str:
    match value:
        case "lookup":
            return "recuperação"
        case "hop":
            return "salto"
        case "compare":
            return "confronto"
        case _ as unreachable:
            return _assert_never(unreachable)


def exhaust_entity_type(value: EntityType) -> str:
    match value:
        case EntityType.PERSON:
            return "pessoa"
        case EntityType.ORG:
            return "organização"
        case EntityType.POLICY:
            return "política"
        case EntityType.DECISION:
            return "decisão"
        case EntityType.INCIDENT:
            return "incidente"
        case EntityType.SYSTEM:
            return "sistema"
        case EntityType.CONCEPT:
            return "conceito"
        case EntityType.SPACE:
            return "espaço"
        case _ as unreachable:
            return _assert_never(unreachable)


def _assert_never(value: Never) -> Never:
    raise ValueError(f"tipo de entidade não tratado: {value}")
