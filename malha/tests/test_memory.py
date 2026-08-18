from mind_shared.types import FeedbackLabel


def test_workspace_isolation(mesh) -> None:
    a = mesh.workspaces.create("alpha", "Alpha")
    b = mesh.workspaces.create("beta", "Beta")
    mesh.ingest_upload(
        a["id"],
        "a.md",
        "# Segredo Alpha\n\nO codigo da cofre Alpha e 111.".encode("utf-8"),
    )
    mesh.ingest_upload(
        b["id"],
        "b.md",
        "# Segredo Beta\n\nO codigo da cofre Beta e 222.".encode("utf-8"),
    )
    result_a = mesh.query(a["id"], "qual o código da cofre Alpha")
    titles = [item.document_title for item in result_a.evidence]
    assert all("Beta" not in title for title in titles)


def test_feedback_changes_ranking(atlas) -> None:
    mesh, workspace_id = atlas
    first = mesh.query(workspace_id, "Quem pode acessar dados de produção da carteira?")
    assert len(first.evidence) >= 2
    leader = first.evidence[0].chunk_id
    other = first.evidence[1].chunk_id
    mesh.mark_feedback(workspace_id, leader, FeedbackLabel.WRONG, first.query_id)
    mesh.mark_feedback(workspace_id, other, FeedbackLabel.USEFUL, first.query_id)
    second = mesh.query(workspace_id, "Quem pode acessar dados de produção da carteira?")
    scores = {item.chunk_id: item.score for item in second.evidence}
    assert scores[other] >= scores.get(leader, 0.0)
