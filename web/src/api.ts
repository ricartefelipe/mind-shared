import type {
  DocumentRow,
  FeedbackLabel,
  GraphSnapshot,
  QueryResult,
  Workspace,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? '/malha'
const SAFE_ID = /^[A-Za-z0-9._-]+$/

export function assertSafeId(value: string): string {
  if (!SAFE_ID.test(value)) {
    throw new Error('identificador inválido')
  }
  return encodeURIComponent(value)
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || response.statusText)
  }
  return (await response.json()) as T
}

export async function listWorkspaces(): Promise<Workspace[]> {
  return parse(await fetch(`${BASE}/workspaces`))
}

export async function listDocuments(workspaceId: string): Promise<DocumentRow[]> {
  const id = assertSafeId(workspaceId)
  return parse(await fetch(`${BASE}/workspaces/${id}/documents`))
}

export async function fetchGraph(workspaceId: string): Promise<GraphSnapshot> {
  const id = assertSafeId(workspaceId)
  return parse(await fetch(`${BASE}/workspaces/${id}/graph`))
}

export async function queryWorkspace(
  workspaceId: string,
  question: string,
  hops: number,
): Promise<QueryResult> {
  const id = assertSafeId(workspaceId)
  return parse(
    await fetch(`${BASE}/workspaces/${id}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, hops }),
    }),
  )
}

export async function sendFeedback(
  workspaceId: string,
  chunkId: string,
  label: FeedbackLabel,
  queryId: string | null,
): Promise<void> {
  const id = assertSafeId(workspaceId)
  await parse(
    await fetch(`${BASE}/workspaces/${id}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chunk_id: chunkId, label, query_id: queryId }),
    }),
  )
}

export async function ingestFile(workspaceId: string, file: File): Promise<unknown> {
  const id = assertSafeId(workspaceId)
  const body = new FormData()
  body.append('file', file)
  return parse(
    await fetch(`${BASE}/workspaces/${id}/ingest`, {
      method: 'POST',
      body,
    }),
  )
}

export async function seedWorkspace(workspaceId: string): Promise<unknown> {
  const id = assertSafeId(workspaceId)
  return parse(
    await fetch(`${BASE}/workspaces/${id}/seed`, {
      method: 'POST',
    }),
  )
}
