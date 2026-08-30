#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Instalando Python + embeddings + LLM local..."
make install-malha-ai

echo "==> Baixando modelo GGUF (primeira vez ~400 MB)..."
malha/.venv/bin/python scripts/download-gguf.py

echo "==> Reindexando corpus com embeddings neurais..."
make reseed-ai

echo ""
echo "IA ligada. Suba a API:"
echo "  make serve-api-ai"
echo ""
echo "Atlas: make serve-web  →  http://127.0.0.1:5173"
echo ""
echo "Confirme no health:"
echo "  curl -s http://127.0.0.1:8000/health | python3 -m json.tool"
echo "  (composer: local, embedding: SentenceEmbedding)"
