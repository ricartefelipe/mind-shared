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
FAITHFULNESS_FLOOR = 0.75
CITATION_PRECISION_FLOOR = 0.70
COMPOSER_TIMEOUT_SECONDS = 8.0
DEMO_WORKSPACE_SLUG = "atlas-norte"
DEMO_TOKEN = "mind-demo-atlas-norte"
TOKEN_HEADER = "X-Mind-Token"


def composer_url() -> str:
    return os.environ.get("MIND_COMPOSER_URL", "").strip()


def composer_model() -> str:
    return os.environ.get("MIND_COMPOSER_MODEL", "local").strip() or "local"


def embedding_model_name() -> str:
    return os.environ.get("MIND_EMBEDDING_MODEL", "").strip()


def embedding_backend_name() -> str:
    return os.environ.get("MIND_EMBEDDING_BACKEND", "").strip()
