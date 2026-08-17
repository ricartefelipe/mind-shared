from mind_shared.graph.extract import classify_name, extract_mentions, extract_relations
from mind_shared.types import EntityType, exhaust_entity_type


def test_extract_policy_and_incident_codes() -> None:
    text = "A norma **P-ACESSO-01** cita INC-2025-04 na Cooperativa Atlas Norte."
    mentions = {name: kind for name, kind in extract_mentions(text)}
    assert any(name.startswith("P-ACESSO") or "P-ACESSO-01" in name for name in mentions)
    assert any("INC-2025-04" in name for name in mentions)
    assert classify_name("P-ACESSO-01") == EntityType.POLICY
    assert classify_name("INC-2025-04") == EntityType.INCIDENT


def test_extract_relations() -> None:
    text = "A Carteira Mind depende de SpringMind para autenticação. N-EVID-02 cita P-ACESSO-01."
    rels = extract_relations(text)
    predicates = {item[1] for item in rels}
    assert "depende_de" in predicates
    assert "cita" in predicates


def test_entity_type_labels_are_exhaustive() -> None:
    labels = {exhaust_entity_type(kind) for kind in EntityType}
    assert "política" in labels
    assert "incidente" in labels
    assert len(labels) == len(EntityType)


def test_graph_persists_entities(atlas) -> None:
    mesh, workspace_id = atlas
    snap = mesh.graph_snapshot(workspace_id)
    names = {item["canonical"] for item in snap["entities"]}
    assert any("atlas" in name for name in names)
    assert snap["relations"]
    assert "conflicts" in snap
    predicates = {item["predicate"] for item in snap["relations"]}
    assert "revoga" in predicates
