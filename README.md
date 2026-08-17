# Mind Shared

**Conhecimento que se acumula, se prova e se compartilha.**

Mind Shared é uma malha cognitiva compartilhada para organizações. Não é um chatbot. É um substrato de conhecimento vivo: documentos entram, viram trechos com metadados de fonte, alimentam um índice híbrido (BM25 + embeddings) e um grafo de entidades, e só então a síntese fala — sempre com evidência, trecho, fonte e score. Sem evidência, a malha recusa.

O diferencial não é “conversar com documentos”. É um sistema nervoso de evidências: recuperação híbrida, travessia multi-hop, proveniência obrigatória, tenancy por espaços e um loop de correção humana no ranking.

## Como rodar

Pré-requisitos: Python 3.12+, Node 22+, Make.

```bash
make install-malha
make install-web
make seed
make serve-api
```

Em outro terminal:

```bash
make serve-web
```

- API: http://127.0.0.1:8000 (docs em `/docs`)
- Atlas: http://127.0.0.1:5173

O corpus de exemplo **Arquivo Atlas Norte** (políticas, decisão PIX, postmortem de autenticação, tenancy e norma de evidências) é ingerido no espaço `atlas-norte` na primeira subida da API ou via `make seed`.

Docker:

```bash
docker compose up --build
```

## Como testar

```bash
make test
```

Isso executa:

- testes do contrato da carteira (`npm test` na raiz)
- `pytest` da malha (chunking, índice, grafo, recuperação, síntese, memória, eval, API)
- `tsc` do atlas (`web`)

Eval isolado, depois do seed:

```bash
cd malha && .venv/bin/python -m mind_shared.cli eval
```

Métricas: **recall@k** (documentos ouro no topo) e **faithfulness** (citações ⊆ evidências recuperadas; perguntas sem resposta devem ser recusadas).

## Arquitetura

```
ingest  → parsers (PDF, Markdown, texto) + chunking com overlap
index   → BM25 esparso + embeddings densos (hashing trick local; sentence-transformers opcional)
graph   → entidades, relações, citações por trecho
retrieve→ fusão RRF, multi-hop no grafo, Evidence[]
synthesize → resposta só com evidências; recusa abaixo do limiar
memory  → workspaces (tenancy) + feedback útil/errada no ranking
eval    → gold set em malha/eval/gold.json
```

Persistência: SQLite local (`MIND_SHARED_DB`, padrão `data/mesh.sqlite`). Sem GPU e sem chaves para o caminho padrão. CI passa com o backend `hash`.

API principal:

- `POST /workspaces` · `GET /workspaces`
- `POST /workspaces/{id}/ingest` (upload)
- `POST /workspaces/{id}/seed`
- `POST /workspaces/{id}/query`
- `POST /workspaces/{id}/feedback`
- `GET /workspaces/{id}/graph`
- `GET /workspaces/{id}/documents`
- `POST /workspaces/{id}/eval`

## Layout do repositório

- `malha/` — motor Python (FastAPI)
- `web/` — atlas de evidências (React + Vite)
- `malha/corpus/` — documentos de demonstração
- `src/` — contrato OpenAPI e mocks MSW da **Carteira Mind**, consumidos pelos frontends da carteira (`@ricartefelipe/mind-wallet-shared`)

## Pacote da carteira

O pacote npm da raiz permanece o contrato compartilhado da Carteira Mind (handlers MSW, PIX, OpenAPI). Instalação local nos frontends:

```json
{
  "devDependencies": {
    "@ricartefelipe/mind-wallet-shared": "file:../mind-shared"
  }
}
```

Após alterar o contrato: `npm run sync:apps`.
