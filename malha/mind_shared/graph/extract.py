from __future__ import annotations

import re

from mind_shared.ingest.parsers import stable_id
from mind_shared.store import Store
from mind_shared.textutil import fold
from mind_shared.types import EntityType, exhaust_entity_type

CODE_RE = re.compile(
    r"\b(P-[A-Z]{3,}-[0-9]{2}|DEC-\d{4}-\d{2}|INC-\d{4}-\d{2}|N-[A-Z]{3,}-\d{2})\b"
)
HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
BOLD_RE = re.compile(r"\*\*([^*]{3,80})\*\*")
TITLE_CASE_RE = re.compile(
    r"\b([A-ZÁÉÍÓÚÂÊÔ][A-Za-zÁÉÍÓÚÂÊÔáéíóúâêôãõç]{2,}"
    r"(?:\s+[A-ZÁÉÍÓÚÂÊÔ][A-Za-zÁÉÍÓÚÂÊÔáéíóúâêôãõç]{2,}){0,3})\b"
)

_RELATION_VERBS: tuple[tuple[str, str], ...] = (
    ("depende de", "depende_de"),
    ("requer", "requer"),
    ("substitui", "substitui"),
    ("revoga", "revoga"),
    ("cita", "cita"),
    ("aponta para", "aponta_para"),
    ("é responsável por", "responsavel_por"),
    ("vive em", "vive_em"),
)

_RELATION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (
        re.compile(
            rf"([^\n.]{{3,80}})\s+{re.escape(verb)}\s+([^\n.]{{3,80}})(?:\.|$)",
            re.IGNORECASE,
        ),
        predicate,
    )
    for verb, predicate in _RELATION_VERBS
)

_PREFIX_TYPES: tuple[tuple[str, EntityType], ...] = (
    ("P-", EntityType.POLICY),
    ("DEC-", EntityType.DECISION),
    ("INC-", EntityType.INCIDENT),
    ("N-", EntityType.POLICY),
)

GAZETTEER: dict[str, EntityType] = {
    "cooperativa atlas norte": EntityType.ORG,
    "atlas norte": EntityType.ORG,
    "carteira mind": EntityType.SYSTEM,
    "mind wallet": EntityType.SYSTEM,
    "springmind": EntityType.SYSTEM,
    "totalrecall": EntityType.SYSTEM,
    "pix": EntityType.CONCEPT,
    "política de acesso a dados": EntityType.POLICY,
    "norma de evidências": EntityType.POLICY,
    "espaço atlas": EntityType.SPACE,
    "tenancy": EntityType.CONCEPT,
}


def classify_name(name: str) -> EntityType:
    folded = fold(name)
    for key, entity_type in GAZETTEER.items():
        if key == folded or key in folded:
            return entity_type
    for prefix, entity_type in _PREFIX_TYPES:
        if name.startswith(prefix):
            return entity_type
    return _type_from_cues(name, folded)


def _type_from_cues(name: str, folded: str) -> EntityType:
    lowered = name.lower()
    if "politica" in folded or "política" in lowered:
        return EntityType.POLICY
    if "decisão" in lowered or "decisao" in folded:
        return EntityType.DECISION
    if "incidente" in folded:
        return EntityType.INCIDENT
    if any(token in folded for token in ("api", "wallet", "msw", "openapi")):
        return EntityType.SYSTEM
    return EntityType.CONCEPT


def extract_mentions(text: str) -> list[tuple[str, EntityType]]:
    found: dict[str, EntityType] = {}
    _collect_codes(text, found)
    _collect_named(text, HEADING_RE, found, min_len=4)
    _collect_named(text, BOLD_RE, found, min_len=3)
    _collect_gazetteer(text, found)
    _collect_title_case(text, found)
    return list(found.items())


def _collect_codes(text: str, found: dict[str, EntityType]) -> None:
    for match in CODE_RE.finditer(text):
        name = match.group(1)
        found[name] = classify_name(name)


def _collect_named(
    text: str,
    pattern: re.Pattern[str],
    found: dict[str, EntityType],
    min_len: int,
) -> None:
    for match in pattern.finditer(text):
        name = match.group(1).strip()
        if len(name) >= min_len:
            found[name] = classify_name(name)


def _collect_gazetteer(text: str, found: dict[str, EntityType]) -> None:
    lowered = fold(text)
    for key, entity_type in GAZETTEER.items():
        if key in lowered:
            label = key.title() if key.islower() else key
            found[label] = entity_type


def _collect_title_case(text: str, found: dict[str, EntityType]) -> None:
    skip = {"o", "a", "os", "as"}
    for match in TITLE_CASE_RE.finditer(text):
        name = match.group(1).strip()
        if name.lower() in skip or len(name) < 5 or name in found:
            continue
        found[name] = classify_name(name)


def extract_relations(text: str) -> list[tuple[str, str, str]]:
    relations: list[tuple[str, str, str]] = []
    for pattern, predicate in _RELATION_PATTERNS:
        for match in pattern.finditer(text):
            src = match.group(1).strip(" \n-*#")
            dst = match.group(2).strip(" \n-*#")
            if 2 < len(src) < 80 and 2 < len(dst) < 80:
                relations.append((src, predicate, dst))
    return relations


def canonical(name: str) -> str:
    return fold(name).strip()


class GraphIndex:
    def __init__(self, store: Store) -> None:
        self.store = store

    def ingest_chunk(self, workspace_id: str, chunk_id: str, text: str) -> None:
        mentions = extract_mentions(text)
        ids: dict[str, str] = {}
        for name, entity_type in mentions:
            entity_id = self._upsert_entity(workspace_id, name, entity_type)
            ids[canonical(name)] = entity_id
            self.store.execute(
                "INSERT OR IGNORE INTO entity_chunks(entity_id, chunk_id) VALUES (?, ?)",
                (entity_id, chunk_id),
            )
        for src, predicate, dst in extract_relations(text):
            src_type = classify_name(src)
            dst_type = classify_name(dst)
            src_id = ids.get(canonical(src)) or self._upsert_entity(workspace_id, src, src_type)
            dst_id = ids.get(canonical(dst)) or self._upsert_entity(workspace_id, dst, dst_type)
            rel_id = stable_id(workspace_id, src_id, predicate, dst_id, chunk_id)
            self.store.execute(
                """
                INSERT OR IGNORE INTO relations(
                  id, workspace_id, src_entity_id, dst_entity_id, predicate, evidence_chunk_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rel_id, workspace_id, src_id, dst_id, predicate, chunk_id),
            )
            _ = exhaust_entity_type(src_type)
            _ = exhaust_entity_type(dst_type)

    def neighbors(self, workspace_id: str, entity_ids: list[str]) -> list[str]:
        if not entity_ids:
            return []
        placeholders = ",".join("?" * len(entity_ids))
        rows = self.store.fetchall(
            f"""
            SELECT DISTINCT CASE
              WHEN src_entity_id IN ({placeholders}) THEN dst_entity_id
              ELSE src_entity_id
            END AS other
            FROM relations
            WHERE workspace_id = ? AND (src_entity_id IN ({placeholders}) OR dst_entity_id IN ({placeholders}))
            """,
            (*entity_ids, workspace_id, *entity_ids, *entity_ids),
        )
        return [row["other"] for row in rows]

    def chunks_for_entities(self, entity_ids: list[str]) -> list[str]:
        if not entity_ids:
            return []
        placeholders = ",".join("?" * len(entity_ids))
        rows = self.store.fetchall(
            f"SELECT DISTINCT chunk_id FROM entity_chunks WHERE entity_id IN ({placeholders})",
            entity_ids,
        )
        return [row["chunk_id"] for row in rows]

    def entities_for_chunks(self, chunk_ids: list[str]) -> list[str]:
        if not chunk_ids:
            return []
        placeholders = ",".join("?" * len(chunk_ids))
        rows = self.store.fetchall(
            f"SELECT DISTINCT entity_id FROM entity_chunks WHERE chunk_id IN ({placeholders})",
            chunk_ids,
        )
        return [row["entity_id"] for row in rows]

    def snapshot(self, workspace_id: str) -> dict[str, list[dict[str, str]]]:
        entities = [
            {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "canonical": row["canonical"],
            }
            for row in self.store.fetchall(
                "SELECT id, name, type, canonical FROM entities WHERE workspace_id = ? ORDER BY name",
                (workspace_id,),
            )
        ]
        relations = [
            {
                "id": row["id"],
                "src": row["src_entity_id"],
                "dst": row["dst_entity_id"],
                "predicate": row["predicate"],
                "evidence_chunk_id": row["evidence_chunk_id"],
            }
            for row in self.store.fetchall(
                """
                SELECT id, src_entity_id, dst_entity_id, predicate, evidence_chunk_id
                FROM relations WHERE workspace_id = ?
                """,
                (workspace_id,),
            )
        ]
        return {"entities": entities, "relations": relations}

    def _upsert_entity(self, workspace_id: str, name: str, entity_type: EntityType) -> str:
        key = canonical(name)
        entity_id = stable_id(workspace_id, key)
        self.store.execute(
            """
            INSERT INTO entities(id, workspace_id, name, type, canonical)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(workspace_id, canonical) DO UPDATE SET name = excluded.name
            """,
            (entity_id, workspace_id, name.strip(), entity_type.value, key),
        )
        return entity_id
