def test_hybrid_retrieve_finds_access_policy(atlas) -> None:
    mesh, workspace_id = atlas
    result = mesh.query(workspace_id, "Quem pode acessar dados de produção da carteira?")
    titles = [item.document_title for item in result.evidence]
    assert any("Política de acesso" in title for title in titles)
    assert result.evidence[0].score > 0
    assert result.evidence[0].source_path
    assert result.evidence[0].excerpt


def test_multihop_pulls_related_chunks(atlas) -> None:
    mesh, workspace_id = atlas
    result = mesh.query(
        workspace_id,
        "O que a norma de evidências exige após o incidente de autenticação?",
        hops=1,
    )
    hops = {item.hop for item in result.evidence}
    titles = " ".join(item.document_title for item in result.evidence)
    assert "N-EVID" in titles or "evidências" in titles.lower() or "Postmortem" in titles
    assert hops <= {0, 1}


def test_provenance_fields_present(atlas) -> None:
    mesh, workspace_id = atlas
    result = mesh.query(workspace_id, "O que é tenancy neste arquivo?")
    item = result.evidence[0]
    assert item.document_id
    assert item.chunk_id
    assert item.start_char >= 0
    assert item.end_char >= item.start_char
