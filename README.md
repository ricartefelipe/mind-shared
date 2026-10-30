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

O seed cria o espaço `atlas-norte` (Arquivo Atlas Norte) e imprime o **token de demo** — isso só
existe no perfil `local` (veja "Perfis, credenciais e papéis" abaixo). Rotas de consulta, ingestão, grafo e eval exigem o header `X-Mind-Token`. O identificador na URL pode ser o slug (`atlas-norte`) ou o id interno.

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

## Perfis, credenciais e papéis

| Perfil (`MIND_PROFILE`) | Para quê | Demo | Criar espaços |
|---|---|---|---|
| `local` (padrão) | máquina do operador, `serve` em `127.0.0.1` | token fixo `mind-demo-atlas-norte` e seed do corpus de exemplo | livre |
| `remote` | instalação exposta a outras pessoas | **não existe**: o token de demo não é emitido nem aceito, o seed responde 404 e o espaço `atlas-norte` não pode ser criado | só com `X-Mind-Admin-Token` igual a `MIND_ADMIN_TOKEN` (obrigatório; sem ele a API não sobe) |

Todo token pertence a **um** espaço: conhecer o id ou o slug de outro espaço não dá acesso. Cada
token tem papel, validade (padrão 90 dias) e pode ser revogado; só o hash fica no banco e a listagem
nunca devolve o valor.

| Papel | Pode |
|---|---|
| `reader` | consultar, ler documentos e grafo |
| `editor` | + ingerir, dar feedback, **excluir documentos** |
| `admin` | + emitir, listar e revogar tokens do espaço |

```http
POST   /workspaces                                      # X-Mind-Admin-Token no perfil remote; devolve o token admin inicial uma vez
POST   /workspaces/{id}/tokens   {"role":"reader","label":"leitor","ttl_days":30}   # admin
GET    /workspaces/{id}/tokens                           # admin (sem o valor dos tokens)
DELETE /workspaces/{id}/tokens/{token_id}                # admin: revoga; o token deixa de valer na hora
DELETE /workspaces/{id}/documents/{document_id}          # editor: remove documento, trechos, BM25, embeddings, grafo e feedback numa transação
```

Pela linha de comando: `mind-shared token --slug atlas-norte --role reader --ttl-days 30`.

## Operação

- **Persistência:** SQLite em WAL com `busy_timeout` de 5 s; escritores concorrentes esperam em vez de
  falhar. Validado com 4 escritores e 3 leitores simultâneos. Para vários processos, o arquivo precisa
  estar em filesystem local (não em NFS/SMB).
- **Backup consistente:** `mind-shared backup <destino.sqlite>` usa a API de backup do SQLite (válida
  com WAL e com escritas em curso). Restaurar é apontar `MIND_SHARED_DB` para a cópia; documentos,
  índices, grafo, tokens e permissões vêm junto — validado por teste que consulta a cópia e obtém as
  mesmas evidências.
- **Exclusão/retificação:** `DELETE .../documents/{id}` é atômico (tudo ou nada) e alcança trechos,
  termos BM25, embeddings, ligações do grafo, entidades/relações que só existiam por aquele documento
  e feedback. O histórico de perguntas guarda só o texto da pergunta. Retificar é excluir e ingerir de
  novo.
- **Rede:** o modo padrão funciona sem internet (composer extrativo e embeddings por hashing). Egress
  só acontece com `MIND_COMPOSER_URL` (Ollama/HTTP) ou modelos externos configurados explicitamente;
  o campo `composer` da resposta diz qual foi usado. Conteúdo de documento é dado, nunca instrução:
  instruções embutidas num documento não mudam o sistema nem revelam tokens (teste
  `test_prompt_injection_in_a_document_is_treated_as_data`).
- **CI (`.github/workflows/ci.yml`):** testes da malha (51), avaliação offline no corpus de exemplo
  (3 casos sem resposta, conflito deliberado entre circular legada e decisão nova), pacote da carteira,
  typecheck/build do atlas, `npm audit` de produção, build e scan bloqueante (HIGH/CRITICAL) da imagem
  da API e prova de que o perfil `remote` não sobe sem token de administração. Nenhuma chamada paga.

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
