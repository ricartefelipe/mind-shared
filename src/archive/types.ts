export type FeedbackLabel = 'useful' | 'wrong'

export type PlanKind = 'lookup' | 'hop' | 'compare'

export type GroundingStatus = 'grounded' | 'conflict' | 'insufficient'

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

export type PlanStep = {
  id: string
  objective: string
  kind: PlanKind
}

export type Contradiction = {
  left_chunk_id: string
  right_chunk_id: string
  subject: string
  left_claim: string
  right_claim: string
  reason: string
}

export type Verification = {
  status: GroundingStatus
  coverage: number
  contradictions: Contradiction[]
  notes: string[]
}

export type QueryResult = {
  query_id: string
  question: string
  answer: {
    text: string
    refused: boolean
    refusal_reason: string | null
    cited_chunk_ids: string[]
    grounding_status: GroundingStatus
  }
  evidence: Evidence[]
  plan: PlanStep[]
  verification: Verification
  composer: 'extractive' | 'http'
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
  conflicts?: Contradiction[]
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

const ENTITY_TYPES = [
  'person',
  'org',
  'policy',
  'decision',
  'incident',
  'system',
  'concept',
  'space',
] as const

type EntityType = (typeof ENTITY_TYPES)[number]

function isEntityType(type: string): type is EntityType {
  return (ENTITY_TYPES as readonly string[]).includes(type)
}

export function entityTypeLabel(type: string): string {
  if (!isEntityType(type)) {
    return type
  }
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
    default: {
      const unreachable: never = type
      return unreachable
    }
  }
}

export function groundingLabel(status: GroundingStatus): string {
  switch (status) {
    case 'grounded':
      return 'fundamentado'
    case 'conflict':
      return 'conflito'
    case 'insufficient':
      return 'insuficiente'
    default: {
      const unreachable: never = status
      return unreachable
    }
  }
}

export function planKindLabel(kind: PlanKind): string {
  switch (kind) {
    case 'lookup':
      return 'recuperação'
    case 'hop':
      return 'salto'
    case 'compare':
      return 'confronto'
    default: {
      const unreachable: never = kind
      return unreachable
    }
  }
}
