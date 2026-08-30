# Mind Shared

**Conhecimento que se acumula, se prova e se compartilha.**

Mind Shared é um arquivo vivo de evidências. Documentos entram, viram trechos com fonte, alimentam um índice híbrido (BM25 + embeddings) e um grafo de entidades. A consulta percorre um ciclo de quatro estágios — plano, recuperação, verificação, síntese — e só fala com trecho, fonte e score. Sem evidência, recusa. Com conflito, relata os dois lados e não escolhe um.

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

- API: http://127.0.0.1:8000 (`/`, `/health`, contrato em `/docs`)
- Atlas: http://127.0.0.1:5173

O seed cria o espaço `atlas-norte` (Arquivo Atlas Norte) e imprime o **token de demo**. Rotas de consulta, ingestão, grafo e eval exigem o header `X-Mind-Token`. O identificador na URL pode ser o slug (`atlas-norte`) ou o id interno.

Token de fixture (não é segredo de produção):

```
X-Mind-Token: mind-demo-atlas-norte
```

Prova da API (depois de `make seed` e `make serve-api`):

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/health
curl -sS -D - -o /tmp/mind-query.json \
  -X POST http://127.0.0.1:8000/workspaces/atlas-norte/query \
  -H 'Content-Type: application/json' \
  -H 'X-Mind-Token: mind-demo-atlas-norte' \
  -d '{"question":"Quem pode acessar dados de produção da carteira?","hops":1}'
```

Esperado: `200` no health e `HTTP/1.1 200 OK` na query.

## Modo IA (estudo)

Instala LLM local (GGUF via `llama-cpp-python`), embeddings neurais (`sentence-transformers`) e reindexa o corpus. Primeira execução baixa o modelo (~400 MB).

```bash
make ai-up          # install + download GGUF + reseed
make serve-api-ai   # API com malha/env.ai
make serve-web      # atlas em outro terminal
```

Confirme em `/health`:

- `composer`: `local` (LLM) ou `http` (Ollama/OpenAI-compatível)
- `embedding`: `SentenceEmbedding`
- `composer_gguf`: caminho do modelo

Variáveis em `malha/env.ai`. Resposta da query inclui `"composer": "local"` quando o LLM gerou o texto.

Modo legado (sem LLM): `make serve-api` (compositor extrativo + embeddings hash).

O atlas local envia esse token por padrão (`VITE_MIND_TOKEN`). O corpus inclui políticas, decisão PIX, postmortem, tenancy, norma de evidências e um conflito deliberado (circular legado vs. decisão nova).

Docker:

```bash
docker compose up --build
```

## Como testar

```bash
make test
```

Isso executa o contrato da carteira, o `pytest` da malha e o typecheck do atlas.

Eval offline, depois do seed:

```bash
cd malha && .venv/bin/python -m mind_shared.cli eval
```

Métricas: **recall@k**, **faithfulness** (citações ⊆ evidências; pergunta sem resposta deve ser recusada) e **citation_precision**. O comando falha se faithfulness cair abaixo do piso (0,75).

## Ciclo cognitivo

```
plan      → subobjetivos de recuperação (regras, sem rede)
retrieve  → BM25 + denso + grafo multi-hop, fusão RRF por subobjetivo
verify    → cobertura, contradições, selo grounded | conflict | insufficient
compose   → síntese com spans ligados a IDs; LLM local, HTTP ou extrativo
```

Compositor (escolha via env, ver `malha/env.ai`):

- **`local`** — GGUF com `llama-cpp-python` (`MIND_COMPOSER_BACKEND=local`)
- **`http`** — API OpenAI-compatível (`MIND_COMPOSER_URL`, ex. Ollama)
- **`extractive`** — padrão sem env de IA; template com citações

Embeddings: hashing por padrão; neurais com `make ai-up` (`MIND_EMBEDDING_BACKEND=sentence`). A imagem Docker pode usar Ollama no `docker-compose.yml`.

Persistência: SQLite (`MIND_SHARED_DB`, padrão `data/mesh.sqlite`).

API:

- `POST /workspaces` — devolve o token uma vez
- `GET /workspaces`
- `POST /workspaces/{id}/ingest` · `POST /workspaces/{id}/seed`
- `POST /workspaces/{id}/query` · `POST /v1/ask`
- `POST /workspaces/{id}/feedback`
- `GET /workspaces/{id}/graph` (entidades, relações, conflitos)
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

Exports adicionais:

- `@ricartefelipe/mind-wallet-shared/archive` — cliente HTTP da malha (`createArchiveClient`)
- `@ricartefelipe/mind-wallet-shared/archive/types` — tipos de evidência, consulta e grafo

Após alterar o contrato: `npm run build` na raiz e `npm run sync:apps` para copiar o OpenAPI da carteira.

### Arquivo na Carteira (ReactMind)

O ReactMind expõe `/arquivo` com consulta, documentos e grafo. Em desenvolvimento:

1. Na pasta `mind-shared`: `make seed && make serve-api`
2. Na pasta `reactmind`: `npm run dev` (proxy `/malha` → API local)
3. Entre na carteira e abra **Arquivo** no menu

Variáveis opcionais no ReactMind: `VITE_MALHA_URL` (padrão `/malha`), `VITE_MIND_TOKEN` (padrão `mind-demo-atlas-norte`).
