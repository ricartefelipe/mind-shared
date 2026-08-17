export type ViewId = 'consulta' | 'arquivo' | 'grafo'

export type FeedbackLabel = 'useful' | 'wrong'

export type Workspace = {
  id: string
  slug: string
  name: string
  created_at: string
}

export type DocumentRow = {
  id: string
  title: string
  source_path: string
  mime: string
  ingested_at: string
  chunks: number
}

export type Evidence = {
  chunk_id: string
  document_id: string
  document_title: string
  source_path: string
  excerpt: string
  score: number
  hop: number
  entity_path: string[]
  start_char: number
  end_char: number
  ordinal: number
}

export type QueryResult = {
  query_id: string
  question: string
  answer: {
    text: string
    refused: boolean
    refusal_reason: string | null
    cited_chunk_ids: string[]
  }
  evidence: Evidence[]
}

export type GraphSnapshot = {
  entities: { id: string; name: string; type: string; canonical: string }[]
  relations: {
    id: string
    src: string
    dst: string
    predicate: string
    evidence_chunk_id: string
  }[]
}

export function viewLabel(view: ViewId): string {
  switch (view) {
    case 'consulta':
      return 'Consulta'
    case 'arquivo':
      return 'Arquivo'
    case 'grafo':
      return 'Grafo'
    default: {
      const unreachable: never = view
      return unreachable
    }
  }
}

export function formatScore(score: number): string {
  return score.toFixed(3)
}

export function hopLabel(hop: number): string {
  if (hop <= 0) {
    return 'salto 0'
  }
  return `salto ${hop}`
}

export function entityTypeLabel(type: string): string {
  switch (type) {
    case 'person':
      return 'pessoa'
    case 'org':
      return 'organização'
    case 'policy':
      return 'política'
    case 'decision':
      return 'decisão'
    case 'incident':
      return 'incidente'
    case 'system':
      return 'sistema'
    case 'concept':
      return 'conceito'
    case 'space':
      return 'espaço'
    default:
      return type
  }
}
