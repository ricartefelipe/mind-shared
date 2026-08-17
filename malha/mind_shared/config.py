from __future__ import annotations

import os
from pathlib import Path


def default_db_path() -> Path:
    raw = os.environ.get("MIND_SHARED_DB", "data/mesh.sqlite")
    return Path(raw).expanduser().resolve()


def corpus_dir() -> Path:
    here = Path(__file__).resolve().parent.parent
    return here / "corpus"


MIN_FUSED_SCORE = 0.012
MIN_CONTENT_OVERLAP = 1
MIN_OVERLAP_RATIO = 0.34
RRF_K = 60
DENSE_DIM = 384
CHUNK_TARGET_CHARS = 420
CHUNK_OVERLAP_CHARS = 90
RETRIEVE_K = 20
EVIDENCE_K = 8
GRAPH_HOPS_DEFAULT = 1
BM25_K1 = 1.5
BM25_B = 0.75
