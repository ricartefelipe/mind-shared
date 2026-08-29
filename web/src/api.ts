import { assertSafeId } from '@ricartefelipe/mind-wallet-shared/archive'
import { createArchiveClient } from '@ricartefelipe/mind-wallet-shared/archive'

const BASE = import.meta.env.VITE_API_URL ?? '/malha'
const TOKEN = import.meta.env.VITE_MIND_TOKEN || 'mind-demo-atlas-norte'

const client = createArchiveClient({ baseUrl: BASE, token: TOKEN })

export { assertSafeId }

export const listWorkspaces = client.listWorkspaces.bind(client)
export const listDocuments = client.listDocuments.bind(client)
export const fetchGraph = client.fetchGraph.bind(client)
export const queryWorkspace = client.queryWorkspace.bind(client)
export const sendFeedback = client.sendFeedback.bind(client)
export const ingestFile = client.ingestFile.bind(client)
export const seedWorkspace = client.seedWorkspace.bind(client)
