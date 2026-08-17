from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from mind_shared.config import FAITHFULNESS_FLOOR, corpus_dir, default_db_path
from mind_shared.engine import Mesh
from mind_shared.eval.harness import run_harness


def main() -> None:
    parser = argparse.ArgumentParser(prog="mind-shared")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    seed = sub.add_parser("seed")
    seed.add_argument("--slug", default="atlas-norte")
    seed.add_argument("--name", default="Arquivo Atlas Norte")
    evaluate = sub.add_parser("eval")
    evaluate.add_argument("--slug", default="atlas-norte")
    args = parser.parse_args()
    if args.cmd == "serve":
        uvicorn.run(
            "mind_shared.api.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=False,
        )
        return
    mesh = Mesh(default_db_path())
    if args.cmd == "seed":
        workspace = mesh.provision_workspace(args.slug, args.name)
        ingested = mesh.ingest_corpus(workspace["id"], corpus_dir())
        print(f"espaço {workspace['slug']}: {len(ingested)} documentos")
        print(f"token de demo (header X-Mind-Token): {workspace['token']}")
        return
    if args.cmd == "eval":
        workspace = mesh.workspaces.by_slug(args.slug)
        if workspace is None:
            raise SystemExit(f"espaço não encontrado: {args.slug}")
        gold = Path(__file__).resolve().parent.parent / "eval" / "gold.json"
        report = run_harness(mesh, workspace["id"], gold)
        print(
            "cases={cases} recall@k={recall:.3f} faithfulness={faith:.3f} "
            "citation_precision={prec:.3f} floor={floor:.2f}".format(
                cases=report["cases"],
                recall=float(report["recall_at_k"]),
                faith=float(report["faithfulness"]),
                prec=float(report["citation_precision"]),
                floor=FAITHFULNESS_FLOOR,
            )
        )
        if float(report["faithfulness"]) < FAITHFULNESS_FLOOR:
            raise SystemExit("faithfulness abaixo do piso")
        return
    raise SystemExit(f"comando desconhecido: {args.cmd}")


if __name__ == "__main__":
    main()
