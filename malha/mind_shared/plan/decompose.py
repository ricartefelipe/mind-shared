from __future__ import annotations

import re

from mind_shared.graph.extract import find_codes
from mind_shared.textutil import fold
from mind_shared.types import PlanKind, PlanStep, exhaust_plan_kind

_SPLIT_WORD = re.compile(r"\s+(?:e|ou|versus|vs)\s+", re.IGNORECASE)
_SPLIT_SEMI = re.compile(r";\s+")
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
    for chunk in _SPLIT_SEMI.split(normalized):
        parts.extend(_SPLIT_WORD.split(chunk))
    return parts


def _cap_kinds(steps: list[PlanStep]) -> list[PlanStep]:
    kinds: tuple[PlanKind, ...] = ("lookup", "hop", "compare")
    for step in steps:
        if step.kind not in kinds:
            raise ValueError(f"tipo de subobjetivo inválido: {step.kind}")
    return steps
