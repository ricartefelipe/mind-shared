import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  fetchGraph,
  ingestFile,
  listDocuments,
  listWorkspaces,
  queryWorkspace,
  seedWorkspace,
  sendFeedback,
} from './api'
import {
  entityTypeLabel,
  formatScore,
  groundingLabel,
  hopLabel,
  planKindLabel,
  viewLabel,
  type DocumentRow,
  type Evidence,
  type GraphSnapshot,
  type QueryResult,
  type ViewId,
  type Workspace,
} from './types'

const PROMPTS = [
  'Quem pode acessar dados de produção da carteira?',
  'Analistas ledger.reader podem acessar dados de produção da carteira?',
  'TotalRecall autentica o usuário na Carteira Mind?',
  'Quando a norma de evidências recusa uma síntese?',
  'Qual o salário do diretor de marketing da cooperativa em 2019?',
]

type ConsultaProps = Readonly<{
  question: string
  hops: number
  busy: boolean
  result: QueryResult | null
  selected: Evidence | null
  onQuestion: (value: string) => void
  onHops: (value: number) => void
  onSubmit: (event: FormEvent) => void
  onSelect: (item: Evidence) => void
  onMark: (label: 'useful' | 'wrong') => void
}>

type ArquivoProps = Readonly<{
  documents: DocumentRow[]
  onUpload: (file: File | undefined) => void
  onSeed: () => void
}>

type GrafoProps = Readonly<{
  snapshot: GraphSnapshot | null
}>

export function App() {
  const [view, setView] = useState<ViewId>('consulta')
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [workspaceId, setWorkspaceId] = useState<string>('')
  const [question, setQuestion] = useState(PROMPTS[0])
  const [hops, setHops] = useState(1)
  const [result, setResult] = useState<QueryResult | null>(null)
  const [selected, setSelected] = useState<Evidence | null>(null)
  const [documents, setDocuments] = useState<DocumentRow[]>([])
  const [graph, setGraph] = useState<GraphSnapshot | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    void bootstrap()
  }, [])

  useEffect(() => {
    if (!workspaceId) {
      return
    }
    void refreshArchive(workspaceId)
  }, [workspaceId, view])

  async function bootstrap() {
    const list = await listWorkspaces()
    setWorkspaces(list)
    if (list[0]) {
      setWorkspaceId(list[0].id)
    }
  }

  async function refreshArchive(id: string) {
    const docs = await listDocuments(id)
    setDocuments(docs)
    if (view === 'grafo') {
      setGraph(await fetchGraph(id))
    }
  }

  async function runQuery(event: FormEvent) {
    event.preventDefault()
    if (!workspaceId || !question.trim()) {
      return
    }
    setBusy(true)
    setNotice(null)
    try {
      const next = await queryWorkspace(workspaceId, question.trim(), hops)
      setResult(next)
      setSelected(next.evidence[0] ?? null)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'falha na consulta')
    } finally {
      setBusy(false)
    }
  }

  async function mark(label: 'useful' | 'wrong') {
    if (!workspaceId || !selected || !result) {
      return
    }
    await sendFeedback(workspaceId, selected.chunk_id, label, result.query_id)
    setNotice(
      label === 'useful'
        ? 'Evidência marcada útil — o ranking aprende.'
        : 'Evidência marcada errada — o ranking penaliza.',
    )
  }

  async function onUpload(file: File | undefined) {
    if (!file || !workspaceId) {
      return
    }
    setBusy(true)
    try {
      await ingestFile(workspaceId, file)
      await refreshArchive(workspaceId)
      setNotice(`Ingerido: ${file.name}`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'falha na ingestão')
    } finally {
      setBusy(false)
    }
  }

  async function onSeed() {
    if (!workspaceId) {
      return
    }
    setBusy(true)
    try {
      await seedWorkspace(workspaceId)
      await refreshArchive(workspaceId)
      setNotice('Corpus Atlas Norte carregado no espaço.')
    } finally {
      setBusy(false)
    }
  }

  const currentWorkspace = workspaces.find((item) => item.id === workspaceId)

  return (
    <div className="sheet">
      <header className="masthead">
        <div className="folio">Tomo I · Arquivo vivo</div>
        <h1>Mind Shared</h1>
        <p className="tagline">Conhecimento que se acumula, se prova e se compartilha.</p>
        <div className="meta-row">
          <span>{currentWorkspace?.name ?? 'sem espaço'}</span>
          <span>{documents.length} documentos</span>
          <span>{busy ? 'indexando…' : 'índice híbrido'}</span>
        </div>
      </header>

      <nav className="ledger-nav" aria-label="seções">
        {(['consulta', 'arquivo', 'grafo'] as const).map((id) => (
          <button
            key={id}
            className={view === id ? 'active' : ''}
            onClick={() => setView(id)}
            type="button"
          >
            {viewLabel(id)}
          </button>
        ))}
      </nav>

      {notice ? <p className="notice">{notice}</p> : null}

      {view === 'consulta' ? (
        <Consulta
          question={question}
          hops={hops}
          busy={busy}
          result={result}
          selected={selected}
          onQuestion={setQuestion}
          onHops={setHops}
          onSubmit={runQuery}
          onSelect={setSelected}
          onMark={mark}
        />
      ) : null}
      {view === 'arquivo' ? (
        <Arquivo documents={documents} onUpload={onUpload} onSeed={onSeed} />
      ) : null}
      {view === 'grafo' ? <Grafo snapshot={graph} /> : null}
    </div>
  )
}

function Consulta({
  question,
  hops,
  busy,
  result,
  selected,
  onQuestion,
  onHops,
  onSubmit,
  onSelect,
  onMark,
}: ConsultaProps) {
  return (
    <div className="split">
      <section className="column">
        <form className="query-box" onSubmit={onSubmit}>
          <label htmlFor="q">Pergunta ao arquivo</label>
          <textarea
            id="q"
            value={question}
            onChange={(event) => onQuestion(event.target.value)}
            rows={3}
          />
          <div className="query-tools">
            <label>
              saltos
              <input
                type="number"
                min={0}
                max={3}
                value={hops}
                onChange={(event) => onHops(Number(event.target.value))}
              />
            </label>
            <button type="submit" disabled={busy}>
              Recuperar evidências
            </button>
          </div>
          <div className="prompt-row">
            {PROMPTS.map((item) => (
              <button key={item} type="button" className="ghost" onClick={() => onQuestion(item)}>
                {item}
              </button>
            ))}
          </div>
        </form>

        {result ? (
          <article
            className={
              result.answer.refused
                ? 'synthesis refused'
                : result.verification.status === 'conflict'
                  ? 'synthesis conflict'
                  : 'synthesis'
            }
          >
            <div className="synthesis-head">
              <h2>
                {result.answer.refused
                  ? 'Recusa fundamentada'
                  : result.verification.status === 'conflict'
                    ? 'Conflito no arquivo'
                    : 'Síntese com proveniência'}
              </h2>
              <span className={`seal ${result.verification.status}`}>
                {groundingLabel(result.verification.status)}
              </span>
            </div>
            {result.plan.length > 0 ? (
              <ol className="plan">
                {result.plan.map((step) => (
                  <li key={step.id}>
                    <span>{planKindLabel(step.kind)}</span>
                    {step.objective}
                  </li>
                ))}
              </ol>
            ) : null}
            <p className="synthesis-body">{result.answer.text}</p>
            {result.answer.refusal_reason ? (
              <p className="reason">{result.answer.refusal_reason}</p>
            ) : null}
            {result.verification.contradictions.length > 0 ? (
              <ul className="conflict-list">
                {result.verification.contradictions.map((item) => (
                  <li key={`${item.left_chunk_id}-${item.right_chunk_id}`}>
                    <strong>{item.subject}</strong>
                    <span>{item.reason}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </article>
        ) : (
          <article className="synthesis idle">
            <h2>O arquivo não conversa. Ele prova.</h2>
            <p>
              Cada afirmação aponta para fonte, trecho e score. Sem evidência, a malha
              cala. O ranking híbrido funde BM25, vizinhança densa e travessia do grafo.
            </p>
          </article>
        )}
      </section>

      <aside className="evidence-rail">
        <h2>Evidências</h2>
        {result?.evidence.map((item, index) => (
          <button
            key={item.chunk_id}
            type="button"
            className={selected?.chunk_id === item.chunk_id ? 'evidence active' : 'evidence'}
            onClick={() => onSelect(item)}
          >
            <span className="index">{String(index + 1).padStart(2, '0')}</span>
            <span className="title">{item.document_title}</span>
            <span className="score">
              peso {formatScore(item.score)} · {hopLabel(item.hop)}
              {result.answer.cited_chunk_ids.includes(item.chunk_id) ? ' · citado' : ''}
            </span>
          </button>
        ))}
        {selected ? (
          <div className="excerpt">
            <p className="source">
              {selected.source_path} · ordinal {selected.ordinal}
            </p>
            <blockquote>{selected.excerpt}</blockquote>
            <div className="marks">
              <button type="button" onClick={() => onMark('useful')}>
                útil
              </button>
              <button type="button" className="danger" onClick={() => onMark('wrong')}>
                errada
              </button>
            </div>
          </div>
        ) : (
          <p className="empty">Nenhuma evidência selecionada.</p>
        )}
      </aside>
    </div>
  )
}

function Arquivo({ documents, onUpload, onSeed }: ArquivoProps) {
  return (
    <section className="archive">
      <div className="archive-tools">
        <label className="file">
          Ingerir PDF, Markdown ou texto
          <input
            type="file"
            accept=".pdf,.md,.markdown,.txt"
            onChange={(event) => onUpload(event.target.files?.[0])}
          />
        </label>
        <button type="button" onClick={onSeed}>
          Carregar corpus Atlas Norte
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Título</th>
            <th>Fonte</th>
            <th>Trechos</th>
            <th>Ingerido</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id}>
              <td>{doc.title}</td>
              <td className="mono">{doc.source_path}</td>
              <td>{doc.chunks}</td>
              <td className="mono">{doc.ingested_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Grafo({ snapshot }: GrafoProps) {
  const layout = useMemo(() => {
    const entities = snapshot?.entities.slice(0, 36) ?? []
    const width = 720
    const height = 520
    const cx = width / 2
    const cy = height / 2
    const radius = 210
    const nodes = entities.map((entity, index) => {
      const angle = (index / Math.max(entities.length, 1)) * Math.PI * 2 - Math.PI / 2
      return {
        ...entity,
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
      }
    })
    const byId = new Map(nodes.map((node) => [node.id, node]))
    const edges = (snapshot?.relations ?? [])
      .map((rel) => {
        const src = byId.get(rel.src)
        const dst = byId.get(rel.dst)
        if (!src || !dst) {
          return null
        }
        return { ...rel, src, dst }
      })
      .filter((item): item is NonNullable<typeof item> => item !== null)
    return { nodes, edges, width, height }
  }, [snapshot])

  if (!snapshot) {
    return <p className="empty">Abra o grafo após ingerir o arquivo.</p>
  }

  return (
    <section className="graph-wrap">
      <svg viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" aria-label="grafo de evidências">
        {layout.edges.map((edge) => (
          <g key={edge.id}>
            <line x1={edge.src.x} y1={edge.src.y} x2={edge.dst.x} y2={edge.dst.y} />
          </g>
        ))}
        {layout.nodes.map((node) => (
          <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
            <circle r={7} />
            <text y={-12}>{node.name.slice(0, 28)}</text>
          </g>
        ))}
      </svg>
      <ul className="legend">
        {snapshot.entities.slice(0, 12).map((entity) => (
          <li key={entity.id}>
            <strong>{entity.name}</strong>
            <span>{entityTypeLabel(entity.type)}</span>
          </li>
        ))}
      </ul>
      {snapshot.conflicts && snapshot.conflicts.length > 0 ? (
        <aside className="graph-conflicts">
          <h2>Conflitos do grafo</h2>
          <ul>
            {snapshot.conflicts.map((item) => (
              <li key={`${item.left_chunk_id}-${item.right_chunk_id}-${item.reason}`}>
                <strong>{item.subject}</strong>
                <p>{item.left_claim}</p>
                <p>{item.right_claim}</p>
                <span>{item.reason}</span>
              </li>
            ))}
          </ul>
        </aside>
      ) : null}
    </section>
  )
}
