import type {
  DocumentRow,
  FeedbackLabel,
  GraphSnapshot,
  QueryResult,
  Workspace,
} from './types'

const BASE = import.meta.env.VITE_API_URL ?? '/malha'

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
  return parse(await fetch(`${BASE}/workspaces/${workspaceId}/documents`))
}

export async function fetchGraph(workspaceId: string): Promise<GraphSnapshot> {
  return parse(await fetch(`${BASE}/workspaces/${workspaceId}/graph`))
}

export async function queryWorkspace(
  workspaceId: string,
  question: string,
  hops: number,
): Promise<QueryResult> {
  return parse(
    await fetch(`${BASE}/workspaces/${workspaceId}/query`, {
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
  await parse(
    await fetch(`${BASE}/workspaces/${workspaceId}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chunk_id: chunkId, label, query_id: queryId }),
    }),
  )
}

export async function ingestFile(workspaceId: string, file: File): Promise<unknown> {
  const body = new FormData()
  body.append('file', file)
  return parse(
    await fetch(`${BASE}/workspaces/${workspaceId}/ingest`, {
      method: 'POST',
      body,
    }),
  )
}

export async function seedWorkspace(workspaceId: string): Promise<unknown> {
  return parse(
    await fetch(`${BASE}/workspaces/${workspaceId}/seed`, {
      method: 'POST',
    }),
  )
}
