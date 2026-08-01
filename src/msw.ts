import { http, HttpResponse, type RequestHandler } from 'msw'

export type MindHandlerOptions = {
  apiBasePath?: string
  systemSlug?: string
}

type MockUser = {
  id: string
  name: string
  email: string
  password: string
}

type Beneficiary = { id: string; name: string; pixKey: string }
type Transaction = {
  id: string
  type: 'PIX_OUT' | 'PIX_IN' | 'TED'
  amountCents: number
  description: string
  createdAt: string
  counterparty: string
}
type Transfer = {
  id: string
  beneficiaryId: string
  amountCents: number
  status: 'COMPLETED'
  createdAt: string
}
type Db = {
  user: MockUser
  availableCents: number
  beneficiaries: Beneficiary[]
  transactions: Transaction[]
  transfers: Transfer[]
  idempotency: Map<string, Transfer>
}

const MOCK_TOKEN = 'mock-jwt-demo'

function createDb(): Db {
  return {
    user: { id: 'u1', name: 'Felipe Demo', email: 'demo@vuemind.dev', password: 'demo123' },
    availableCents: 250_000,
    beneficiaries: [
      { id: 'b1', name: 'Ana Silva', pixKey: 'ana@email.com' },
      { id: 'b2', name: 'Mercado Central', pixKey: '11222333000181' },
    ],
    transactions: [
      {
        id: 't1',
        type: 'PIX_IN',
        amountCents: 50_000,
        description: 'Recebido',
        createdAt: '2026-07-20T10:00:00.000Z',
        counterparty: 'Carlos',
      },
    ],
    transfers: [],
    idempotency: new Map(),
  }
}

function correlationId(): string {
  return crypto.randomUUID()
}

function error(code: string, message: string, id = correlationId()) {
  return { code, message, correlationId: id }
}

function endpoint(basePath: string, path: string): string {
  return `*${basePath}${path}`
}

export function createMindHandlers(options: MindHandlerOptions = {}): RequestHandler[] {
  const apiBasePath = options.apiBasePath ?? '/api/v1'
  const db = createDb()

  return [
    http.post(endpoint(apiBasePath, '/auth/login'), async ({ request }) => {
      const body = (await request.json()) as { email: string; password: string }
      if (body.email !== db.user.email || body.password !== db.user.password) {
        return HttpResponse.json(
          error(
            'INVALID_CREDENTIALS',
            'Email ou senha inválidos.',
            request.headers.get('X-Correlation-Id') ?? correlationId(),
          ),
          { status: 401 },
        )
      }
      return HttpResponse.json({
        accessToken: MOCK_TOKEN,
        user: { id: db.user.id, name: db.user.name, email: db.user.email },
      })
    }),
    http.get(endpoint(apiBasePath, '/wallet/balance'), () =>
      HttpResponse.json({ availableCents: db.availableCents, currency: 'BRL' }),
    ),
    http.get(endpoint(apiBasePath, '/wallet/transactions'), ({ request }) => {
      const url = new URL(request.url)
      const from = url.searchParams.get('from')
      const to = url.searchParams.get('to')
      const type = url.searchParams.get('type')
      const items = db.transactions.filter((transaction) => {
        if (from && transaction.createdAt < from) return false
        if (to && transaction.createdAt > to) return false
        return !type || type === 'ALL' || transaction.type === type
      })
      return HttpResponse.json({ items })
    }),
    http.get(endpoint(apiBasePath, '/beneficiaries'), () =>
      HttpResponse.json({ items: db.beneficiaries }),
    ),
    http.post(endpoint(apiBasePath, '/beneficiaries'), async ({ request }) => {
      const body = (await request.json()) as { name: string; pixKey: string }
      if (!body.name?.trim() || !body.pixKey?.trim()) {
        return HttpResponse.json(
          error(
            'INVALID_BENEFICIARY',
            'Nome e chave PIX são obrigatórios.',
            request.headers.get('X-Correlation-Id') ?? correlationId(),
          ),
          { status: 400 },
        )
      }
      const beneficiary = { id: crypto.randomUUID(), name: body.name, pixKey: body.pixKey }
      db.beneficiaries.push(beneficiary)
      return HttpResponse.json(beneficiary, { status: 201 })
    }),
    http.delete(endpoint(apiBasePath, '/beneficiaries/:id'), ({ params }) => {
      const index = db.beneficiaries.findIndex((item) => item.id === params.id)
      if (index === -1) {
        return HttpResponse.json(
          error('BENEFICIARY_NOT_FOUND', 'Favorecido não encontrado.'),
          { status: 404 },
        )
      }
      db.beneficiaries.splice(index, 1)
      return new HttpResponse(null, { status: 204 })
    }),
    http.post(endpoint(apiBasePath, '/transfers/pix'), async ({ request }) => {
      const idempotencyKey = request.headers.get('Idempotency-Key') ?? crypto.randomUUID()
      const body = (await request.json()) as { beneficiaryId: string; amountCents: number }
      const cached = db.idempotency.get(idempotencyKey)
      if (cached) return HttpResponse.json(cached, { status: 201 })
      const beneficiary = db.beneficiaries.find((item) => item.id === body.beneficiaryId)
      const requestCorrelationId = request.headers.get('X-Correlation-Id') ?? correlationId()
      if (!beneficiary) {
        return HttpResponse.json(
          error('BENEFICIARY_NOT_FOUND', 'Favorecido não encontrado.', requestCorrelationId),
          { status: 400 },
        )
      }
      if (!Number.isInteger(body.amountCents) || body.amountCents <= 0) {
        return HttpResponse.json(
          error('INVALID_AMOUNT', 'O valor da transferência deve ser positivo.', requestCorrelationId),
          { status: 400 },
        )
      }
      if (db.availableCents < body.amountCents) {
        return HttpResponse.json(
          error(
            'INSUFFICIENT_FUNDS',
            'Saldo insuficiente para completar essa transferência.',
            requestCorrelationId,
          ),
          { status: 409 },
        )
      }
      db.availableCents -= body.amountCents
      const transfer: Transfer = {
        id: crypto.randomUUID(),
        beneficiaryId: body.beneficiaryId,
        amountCents: body.amountCents,
        status: 'COMPLETED',
        createdAt: new Date().toISOString(),
      }
      db.transfers.push(transfer)
      db.transactions.unshift({
        id: crypto.randomUUID(),
        type: 'PIX_OUT',
        amountCents: body.amountCents,
        description: `PIX para ${beneficiary.name}`,
        createdAt: transfer.createdAt,
        counterparty: beneficiary.name,
      })
      db.idempotency.set(idempotencyKey, transfer)
      return HttpResponse.json(transfer, { status: 201 })
    }),
    http.get(endpoint(apiBasePath, '/transfers/:id'), ({ params }) => {
      const transfer = db.transfers.find((item) => item.id === params.id)
      if (!transfer) {
        return HttpResponse.json(
          error('TRANSFER_NOT_FOUND', 'Erro ao processar a transferência.'),
          { status: 404 },
        )
      }
      return HttpResponse.json(transfer)
    }),
  ]
}
