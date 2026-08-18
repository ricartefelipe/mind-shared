from __future__ import annotations

from mind_shared.graph.extract import find_codes
from mind_shared.textutil import fold
from mind_shared.types import PlanKind, PlanStep, exhaust_plan_kind

_SPLIT_WORDS = frozenset({"e", "ou", "versus", "vs"})
_HOP_CUES = (
    "apos",
    "depois",
    "incidente",
    "relacionad",
    "depende",
    "cita",
    "norma",
    "postmortem",
)
_COMPARE_CUES = (
    "conflito",
    "revoga",
    "ainda vale",
    "podem acessar",
    "nao podem",
    "ou a decisao",
    "versus",
    "legado",
)


def decompose(question: str) -> tuple[PlanStep, ...]:
    cleaned = " ".join(question.split())
    if not cleaned:
        return (PlanStep(id="q0", objective="arquivo", kind="lookup"),)
    steps: list[PlanStep] = [
        PlanStep(id="q0", objective=cleaned, kind="lookup"),
    ]
    folded = fold(cleaned)
    for index, code in enumerate(find_codes(cleaned), start=1):
        steps.append(
            PlanStep(
                id=f"code{index}",
                objective=f"trechos que citam {code}",
                kind="lookup",
            )
        )
    clauses = [part.strip(" ?.") for part in _split_clauses(cleaned) if len(part.strip(" ?.")) > 12]
    if len(clauses) >= 2:
        for index, clause in enumerate(clauses[:3], start=1):
            steps.append(
                PlanStep(id=f"cl{index}", objective=clause, kind="lookup"),
            )
    if any(cue in folded for cue in _HOP_CUES):
        steps.append(
            PlanStep(
                id="hop",
                objective=f"contexto ligado no grafo: {cleaned}",
                kind="hop",
            )
        )
    if any(cue in folded for cue in _COMPARE_CUES):
        steps.append(
            PlanStep(
                id="cmp",
                objective=f"posições incompatíveis sobre: {cleaned}",
                kind="compare",
            )
        )
    unique: list[PlanStep] = []
    seen: set[str] = set()
    for step in steps:
        key = fold(step.objective)
        if key in seen:
            continue
        seen.add(key)
        _ = exhaust_plan_kind(step.kind)
        unique.append(step)
    return tuple(_cap_kinds(unique[:6]))


def _split_clauses(text: str) -> list[str]:
    normalized = text.replace("vs.", "vs").replace("VS.", "vs")
    parts: list[str] = []
    for chunk in normalized.split("; "):
        parts.extend(_split_conjunctions(chunk))
    return parts


def _split_conjunctions(text: str) -> list[str]:
    words = text.split()
    if not words:
        return [text] if text else []
    parts: list[str] = []
    current: list[str] = []
    for word in words:
        if word.lower() in _SPLIT_WORDS and current:
            parts.append(" ".join(current))
            current = []
        else:
            current.append(word)
    if current:
        parts.append(" ".join(current))
    return parts


def _cap_kinds(steps: list[PlanStep]) -> list[PlanStep]:
    kinds: tuple[PlanKind, ...] = ("lookup", "hop", "compare")
    for step in steps:
        if step.kind not in kinds:
            raise ValueError(f"tipo de subobjetivo inválido: {step.kind}")
    return steps
