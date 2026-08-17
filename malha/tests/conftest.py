from __future__ import annotations

from pathlib import Path

import pytest

from mind_shared.config import corpus_dir
from mind_shared.engine import Mesh


@pytest.fixture
def mesh(tmp_path: Path) -> Mesh:
    return Mesh(tmp_path / "mesh.sqlite")


@pytest.fixture
def atlas(mesh: Mesh) -> tuple[Mesh, str]:
    workspace = mesh.workspaces.create("atlas-norte", "Arquivo Atlas Norte")
    mesh.ingest_corpus(workspace["id"], corpus_dir())
    return mesh, workspace["id"]
