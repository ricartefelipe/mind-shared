#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO_ID = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"


def main() -> None:
    from huggingface_hub import hf_hub_download

    root = Path(__file__).resolve().parent.parent
    dest = root / "malha" / "models"
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / FILENAME
    if target.is_file():
        print(f"modelo já existe: {target}")
        return
    print(f"baixando {REPO_ID}/{FILENAME} (~400 MB)...")
    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=FILENAME,
        local_dir=str(dest),
    )
    print(f"modelo salvo em {path}")


if __name__ == "__main__":
    main()
