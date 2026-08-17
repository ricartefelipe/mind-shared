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
TITLE_CASE_RE = re.compile(r"\b([A-ZÁÉÍÓÚÂÊÔ][\wÁÉÍÓÚÂÊÔáéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔ][\wÁÉÍÓÚÂÊÔáéíóúâêôãõç]+){0,4})\b")

RELATION_SPECS: tuple[tuple[str, str], ...] = (
    (r"(.+?)\s+depende de\s+(.+?)(?:\.|$)", "depende_de"),
    (r"(.+?)\s+requer\s+(.+?)(?:\.|$)", "requer"),
    (r"(.+?)\s+substitui\s+(.+?)(?:\.|$)", "substitui"),
    (r"(.+?)\s+revoga\s+(.+?)(?:\.|$)", "revoga"),
    (r"(.+?)\s+cita\s+(.+?)(?:\.|$)", "cita"),
    (r"(.+?)\s+aponta para\s+(.+?)(?:\.|$)", "aponta_para"),
    (r"(.+?)\s+é responsável por\s+(.+?)(?:\.|$)", "responsavel_por"),
    (r"(.+?)\s+vive em\s+(.+?)(?:\.|$)", "vive_em"),
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
    if name.startswith("P-") or "politica" in folded or "política" in name.lower():
        return EntityType.POLICY
    if name.startswith("DEC-") or "decisão" in name.lower() or "decisao" in folded:
        return EntityType.DECISION
    if name.startswith("INC-") or "incidente" in folded:
        return EntityType.INCIDENT
    if name.startswith("N-"):
        return EntityType.POLICY
    if any(token in folded for token in ("api", "wallet", "msw", "openapi")):
        return EntityType.SYSTEM
    return EntityType.CONCEPT


def extract_mentions(text: str) -> list[tuple[str, EntityType]]:
    found: dict[str, EntityType] = {}
    for match in CODE_RE.finditer(text):
        found[match.group(1)] = classify_name(match.group(1))
    for match in HEADING_RE.finditer(text):
        name = match.group(1).strip()
        if len(name) >= 4:
            found[name] = classify_name(name)
    for match in BOLD_RE.finditer(text):
        name = match.group(1).strip()
        if len(name) >= 3:
            found[name] = classify_name(name)
    lowered = fold(text)
    for key, entity_type in GAZETTEER.items():
        if key in lowered:
            found[key.title() if key.islower() else key] = entity_type
    for match in TITLE_CASE_RE.finditer(text):
        name = match.group(1).strip()
        if name.lower() in {"o", "a", "os", "as"} or len(name) < 5:
            continue
        if name not in found:
            found[name] = classify_name(name)
    return [(name, entity_type) for name, entity_type in found.items()]


def extract_relations(text: str) -> list[tuple[str, str, str]]:
    relations: list[tuple[str, str, str]] = []
    for pattern, predicate in RELATION_SPECS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
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
