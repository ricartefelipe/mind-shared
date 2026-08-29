import type {
  DocumentRow,
  FeedbackLabel,
  GraphSnapshot,
  QueryResult,
  Workspace,
} from './types.js'

const SAFE_ID = /^[A-Za-z0-9._-]+$/

export function assertSafeId(value: string): string {
  if (!SAFE_ID.test(value)) {
    throw new Error('identificador inválido')
  }
  return encodeURIComponent(value)
}

export type ArchiveClientOptions = {
  baseUrl: string
  token: string
}

export type ArchiveClient = ReturnType<typeof createArchiveClient>

export function createArchiveClient(options: ArchiveClientOptions) {
  const base = options.baseUrl.replace(/\/$/, '')
  const token = options.token

  function authHeaders(extra?: Record<string, string>): Record<string, string> {
    return { 'X-Mind-Token': token, ...extra }
  }

  async function parse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || response.statusText)
    }
    return (await response.json()) as T
  }

  return {
    async listWorkspaces(): Promise<Workspace[]> {
      return parse(await fetch(`${base}/workspaces`))
    },

    async listDocuments(workspaceId: string): Promise<DocumentRow[]> {
      const id = assertSafeId(workspaceId)
      return parse(
        await fetch(`${base}/workspaces/${id}/documents`, { headers: authHeaders() }),
      )
    },

    async fetchGraph(workspaceId: string): Promise<GraphSnapshot> {
      const id = assertSafeId(workspaceId)
      return parse(
        await fetch(`${base}/workspaces/${id}/graph`, { headers: authHeaders() }),
      )
    },

    async queryWorkspace(
      workspaceId: string,
      question: string,
      hops: number,
    ): Promise<QueryResult> {
      const id = assertSafeId(workspaceId)
      return parse(
        await fetch(`${base}/workspaces/${id}/query`, {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ question, hops }),
        }),
      )
    },

    async sendFeedback(
      workspaceId: string,
      chunkId: string,
      label: FeedbackLabel,
      queryId: string | null,
    ): Promise<void> {
      const id = assertSafeId(workspaceId)
      await parse(
        await fetch(`${base}/workspaces/${id}/feedback`, {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ chunk_id: chunkId, label, query_id: queryId }),
        }),
      )
    },

    async ingestFile(workspaceId: string, file: File): Promise<unknown> {
      const id = assertSafeId(workspaceId)
      const body = new FormData()
      body.append('file', file)
      return parse(
        await fetch(`${base}/workspaces/${id}/ingest`, {
          method: 'POST',
          headers: authHeaders(),
          body,
        }),
      )
    },

    async seedWorkspace(workspaceId: string): Promise<unknown> {
      const id = assertSafeId(workspaceId)
      return parse(
        await fetch(`${base}/workspaces/${id}/seed`, {
          method: 'POST',
          headers: authHeaders(),
        }),
      )
    },
  }
}
