import { http, HttpResponse, type RequestHandler } from 'msw'
import { assertValidPixKey, type PixKeyType } from './pixKey.js'
import { buildQrPayload } from './qrPayload.js'

export type MindHandlerOptions = {
  apiBasePath?: string
  systemSlug?: string
  users?: MindUserStore
}

export type MindUser = {
  id: string
  name: string
  email: string
  password: string
  enabled: boolean
  role?: string
  expiresAt?: string
}

export type MindUserStore = Map<string, MindUser>

export type TotalRecallUserRequest = {
  email: string
  name?: string
  password?: string
  role?: string
  expiresAt?: string
  action?: 'upsert' | 'disable' | 'revoke'
}

type Beneficiary = {
  id: string
  name: string
  pixKey: string
  pixKeyType: PixKeyType
}

type Transaction = {
  id: string
  type: 'PIX_OUT' | 'PIX_IN' | 'TED'
  amountCents: number
  description: string
  createdAt: string
  counterparty: string
}

type TransferStatus = 'COMPLETED' | 'SCHEDULED' | 'FAILED'

type Transfer = {
  id: string
  beneficiaryId?: string
  pixKey?: string
  pixKeyType?: PixKeyType
  amountCents: number
  status: TransferStatus
  createdAt: string
  scheduledFor?: string
  endToEndId: string
  correlationId: string
}

type Notification = {
  id: string
  title: string
  body: string
  read: boolean
  createdAt: string
}

type OnboardingStepId = 'PROFILE_OK' | 'FIRST_BENEFICIARY' | 'FIRST_PIX' | 'VIEW_STATEMENT'

type OnboardingStep = {
  id: OnboardingStepId
  done: boolean
}

type OnboardingState = {
  steps: OnboardingStep[]
  completed: boolean
}

type Db = {
  users: MindUserStore
  availableCents: number
  blockedCents: number
  dailyLimitCents: number
  dailySpentCents: number
  beneficiaries: Beneficiary[]
  transactions: Transaction[]
  transfers: Transfer[]
  notifications: Notification[]
  onboarding: OnboardingState
  idempotency: Map<string, Transfer>
}

const MOCK_TOKEN = 'mock-jwt-demo'

const ONBOARDING_STEP_IDS: OnboardingStepId[] = [
  'PROFILE_OK',
  'FIRST_BENEFICIARY',
  'FIRST_PIX',
  'VIEW_STATEMENT',
]

function createOnboardingState(): OnboardingState {
  return {
    steps: ONBOARDING_STEP_IDS.map((id) => ({ id, done: false })),
    completed: false,
  }
}

function markOnboardingStep(onboarding: OnboardingState, stepId: OnboardingStepId): void {
  const step = onboarding.steps.find((item) => item.id === stepId)
  if (step) {
    step.done = true
  }
  onboarding.completed = onboarding.steps.every((item) => item.done)
}

function createDb(): Db {
  return {
    users: createMindUserStore(),
    availableCents: 250_000,
    blockedCents: 10_000,
    dailyLimitCents: 100_000,
    dailySpentCents: 0,
    beneficiaries: [
      { id: 'b1', name: 'Ana Silva', pixKey: 'ana@email.com', pixKeyType: 'EMAIL' },
      { id: 'b2', name: 'Mercado Central', pixKey: '11222333000', pixKeyType: 'CPF' },
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
      {
        id: 't2',
        type: 'PIX_OUT',
        amountCents: 15_000,
        description: 'Pagamento mercado',
        createdAt: '2026-07-21T11:00:00.000Z',
        counterparty: 'Mercado Central',
      },
      {
        id: 't3',
        type: 'TED',
        amountCents: 80_000,
        description: 'Transferência TED',
        createdAt: '2026-07-22T09:30:00.000Z',
        counterparty: 'Banco Exemplo',
      },
      {
        id: 't4',
        type: 'PIX_IN',
        amountCents: 25_000,
        description: 'Estorno parcial',
        createdAt: '2026-07-23T14:15:00.000Z',
        counterparty: 'Ana Silva',
      },
      {
        id: 't5',
        type: 'PIX_OUT',
        amountCents: 5_000,
        description: 'Café da manhã',
        createdAt: '2026-07-24T08:00:00.000Z',
        counterparty: 'Padaria Sol',
      },
    ],
    transfers: [],
    notifications: [
      {
        id: 'n1',
        title: 'PIX recebido',
        body: 'Você recebeu um PIX de R$ 500,00 de Carlos.',
        read: false,
        createdAt: '2026-07-20T10:00:05.000Z',
      },
      {
        id: 'n2',
        title: 'Limite diário próximo',
        body: 'Você já utilizou uma parte relevante do seu limite diário de PIX.',
        read: false,
        createdAt: '2026-07-24T18:00:00.000Z',
      },
      {
        id: 'n3',
        title: 'Complete seu onboarding',
        body: 'Cadastre um favorecido e faça seu primeiro PIX para liberar todo o app.',
        read: false,
        createdAt: '2026-07-25T09:00:00.000Z',
      },
    ],
    onboarding: createOnboardingState(),
    idempotency: new Map(),
  }
}

export function createMindUserStore(): MindUserStore {
  return new Map([
    [
      'demo@vuemind.dev',
      {
        id: 'u1',
        name: 'Felipe Demo',
        email: 'demo@vuemind.dev',
        password: 'demo123',
        enabled: true,
      },
    ],
  ])
}

export function provisionMindUser(
  users: MindUserStore,
  request: TotalRecallUserRequest,
): MindUser {
  const action = request.action ?? 'upsert'
  const existing = users.get(request.email)

  if (action === 'upsert') {
    if (!request.email?.trim() || !request.name?.trim() || !request.password?.trim()) {
      throw new Error('Email, nome e senha são obrigatórios para provisionar um usuário.')
    }
    const user: MindUser = {
      id: existing?.id ?? request.email,
      email: request.email,
      name: request.name,
      password: request.password,
      enabled: true,
      role: request.role,
      expiresAt: request.expiresAt,
    }
    users.set(user.email, user)
    return user
  }

  if (!existing) {
    throw new Error('Usuário não encontrado.')
  }

  const user: MindUser = {
    ...existing,
    enabled: false,
    expiresAt: action === 'revoke' ? new Date().toISOString() : existing.expiresAt,
  }
  users.set(user.email, user)
  return user
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

function resolveTransferCounterparty(db: Db, transfer: Transfer): string {
  if (transfer.beneficiaryId) {
    const beneficiary = db.beneficiaries.find((item) => item.id === transfer.beneficiaryId)
    if (beneficiary) return beneficiary.name
  }
  return transfer.pixKey ?? 'Destinatário'
}

function completeTransfer(db: Db, transfer: Transfer, nowIso: string): void {
  db.availableCents -= transfer.amountCents
  db.dailySpentCents += transfer.amountCents
  transfer.status = 'COMPLETED'
  const counterparty = resolveTransferCounterparty(db, transfer)
  db.transactions.unshift({
    id: crypto.randomUUID(),
    type: 'PIX_OUT',
    amountCents: transfer.amountCents,
    description: `PIX para ${counterparty}`,
    createdAt: nowIso,
    counterparty,
  })
  markOnboardingStep(db.onboarding, 'FIRST_PIX')
  db.notifications.unshift({
    id: crypto.randomUUID(),
    title: 'PIX enviado',
    body: `Transferência de ${transfer.amountCents} centavos para ${counterparty} foi concluída.`,
    read: false,
    createdAt: nowIso,
  })
}

function processDueScheduledTransfers(db: Db, now = new Date()): void {
  const nowIso = now.toISOString()
  for (const transfer of db.transfers) {
    if (transfer.status !== 'SCHEDULED' || !transfer.scheduledFor) continue
    if (transfer.scheduledFor > nowIso) continue
    if (db.availableCents < transfer.amountCents) {
      transfer.status = 'FAILED'
      db.notifications.unshift({
        id: crypto.randomUUID(),
        title: 'Transferência agendada falhou',
        body: 'Saldo insuficiente para concluir a transferência agendada.',
        read: false,
        createdAt: nowIso,
      })
      continue
    }
    if (db.dailySpentCents + transfer.amountCents > db.dailyLimitCents) {
      transfer.status = 'FAILED'
      db.notifications.unshift({
        id: crypto.randomUUID(),
        title: 'Transferência agendada falhou',
        body: 'Limite diário insuficiente para concluir a transferência agendada.',
        read: false,
        createdAt: nowIso,
      })
      continue
    }
    completeTransfer(db, transfer, nowIso)
  }
}

export function createMindHandlers(options: MindHandlerOptions = {}): RequestHandler[] {
  const apiBasePath = options.apiBasePath ?? '/api/v1'
  const db = createDb()
  if (options.users) {
    db.users = options.users
  }

  return [
    http.post(endpoint(apiBasePath, '/auth/login'), async ({ request }) => {
      const body = (await request.json()) as { email: string; password: string }
      const user = db.users.get(body.email)
      const isExpired = user?.expiresAt ? new Date(user.expiresAt) <= new Date() : false
      if (!user || !user.enabled || isExpired || body.password !== user.password) {
        return HttpResponse.json(
          error(
            'INVALID_CREDENTIALS',
            'Email ou senha inválidos.',
            request.headers.get('X-Correlation-Id') ?? correlationId(),
          ),
          { status: 401 },
        )
      }
      markOnboardingStep(db.onboarding, 'PROFILE_OK')
      return HttpResponse.json({
        accessToken: MOCK_TOKEN,
        user: { id: user.id, name: user.name, email: user.email },
      })
    }),
    http.post('*/internal/v1/totalrecall/users', async ({ request }) => {
      const body = (await request.json()) as TotalRecallUserRequest
      try {
        const user = provisionMindUser(db.users, body)
        return HttpResponse.json({
          id: user.id,
          email: user.email,
          name: user.name,
          enabled: user.enabled,
          ...(user.role ? { role: user.role } : {}),
          ...(user.expiresAt ? { expiresAt: user.expiresAt } : {}),
        })
      } catch (exception) {
        const message = exception instanceof Error ? exception.message : 'Requisição de provisionamento inválida.'
        return HttpResponse.json(error('INVALID_PROVISION_REQUEST', message), { status: 400 })
      }
    }),
    http.get(endpoint(apiBasePath, '/wallet/balance'), () => {
      processDueScheduledTransfers(db)
      return HttpResponse.json({
        availableCents: db.availableCents,
        blockedCents: db.blockedCents,
        dailyLimitCents: db.dailyLimitCents,
        dailySpentCents: db.dailySpentCents,
        currency: 'BRL',
      })
    }),
    http.get(endpoint(apiBasePath, '/wallet/transactions'), ({ request }) => {
      const url = new URL(request.url)
      const from = url.searchParams.get('from')
      const to = url.searchParams.get('to')
      const type = url.searchParams.get('type')
      const q = url.searchParams.get('q')?.trim().toLowerCase() ?? ''
      const page = Math.max(1, Number.parseInt(url.searchParams.get('page') ?? '1', 10) || 1)
      const pageSize = Math.max(
        1,
        Math.min(100, Number.parseInt(url.searchParams.get('pageSize') ?? '20', 10) || 20),
      )
      const filtered = db.transactions.filter((transaction) => {
        if (from && transaction.createdAt < from) return false
        if (to && transaction.createdAt > to) return false
        if (type && type !== 'ALL' && transaction.type !== type) return false
        if (
          q &&
          !transaction.description.toLowerCase().includes(q) &&
          !transaction.counterparty.toLowerCase().includes(q)
        ) {
          return false
        }
        return true
      })
      const total = filtered.length
      const start = (page - 1) * pageSize
      const items = filtered.slice(start, start + pageSize)
      markOnboardingStep(db.onboarding, 'VIEW_STATEMENT')
      return HttpResponse.json({ items, page, pageSize, total })
    }),
    http.get(endpoint(apiBasePath, '/me/onboarding'), () =>
      HttpResponse.json({
        steps: db.onboarding.steps,
        completed: db.onboarding.completed,
      }),
    ),
    http.get(endpoint(apiBasePath, '/beneficiaries'), () =>
      HttpResponse.json({ items: db.beneficiaries }),
    ),
    http.post(endpoint(apiBasePath, '/beneficiaries'), async ({ request }) => {
      const body = (await request.json()) as {
        name: string
        pixKey: string
        pixKeyType?: PixKeyType
      }
      const requestCorrelationId = request.headers.get('X-Correlation-Id') ?? correlationId()
      if (!body.name?.trim() || !body.pixKey?.trim() || !body.pixKeyType) {
        return HttpResponse.json(
          error(
            'INVALID_BENEFICIARY',
            'Nome, chave PIX e tipo da chave são obrigatórios.',
            requestCorrelationId,
          ),
          { status: 400 },
        )
      }
      try {
        assertValidPixKey(body.pixKeyType, body.pixKey)
      } catch {
        return HttpResponse.json(
          error('INVALID_PIX_KEY', 'Chave PIX inválida para o tipo informado.', requestCorrelationId),
          { status: 400 },
        )
      }
      const beneficiary: Beneficiary = {
        id: crypto.randomUUID(),
        name: body.name,
        pixKey: body.pixKey,
        pixKeyType: body.pixKeyType,
      }
      db.beneficiaries.push(beneficiary)
      markOnboardingStep(db.onboarding, 'FIRST_BENEFICIARY')
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
      const idempotencyKey = request.headers.get('Idempotency-Key')
      if (idempotencyKey) {
        const cached = db.idempotency.get(idempotencyKey)
        if (cached) return HttpResponse.json(cached, { status: 201 })
      }

      const body = (await request.json()) as {
        beneficiaryId?: string
        pixKey?: string
        pixKeyType?: PixKeyType
        amountCents: number
        scheduledFor?: string
      }
      const requestCorrelationId = request.headers.get('X-Correlation-Id') ?? correlationId()
      const hasBeneficiary = Boolean(body.beneficiaryId?.trim())
      const hasPixKeyPair = Boolean(body.pixKey?.trim() && body.pixKeyType)

      if (hasBeneficiary === hasPixKeyPair) {
        return HttpResponse.json(
          error(
            'VALIDATION_ERROR',
            'Informe beneficiaryId ou o par pixKey + pixKeyType, nunca ambos.',
            requestCorrelationId,
          ),
          { status: 400 },
        )
      }

      if (!Number.isInteger(body.amountCents) || body.amountCents <= 0) {
        return HttpResponse.json(
          error(
            'VALIDATION_ERROR',
            'O valor da transferência deve ser um inteiro positivo.',
            requestCorrelationId,
          ),
          { status: 400 },
        )
      }

      let beneficiaryId: string | undefined
      let pixKey: string | undefined
      let pixKeyType: PixKeyType | undefined
      let counterparty = 'Destinatário'

      if (hasBeneficiary) {
        const beneficiary = db.beneficiaries.find((item) => item.id === body.beneficiaryId)
        if (!beneficiary) {
          return HttpResponse.json(
            error('BENEFICIARY_NOT_FOUND', 'Favorecido não encontrado.', requestCorrelationId),
            { status: 400 },
          )
        }
        beneficiaryId = beneficiary.id
        pixKey = beneficiary.pixKey
        pixKeyType = beneficiary.pixKeyType
        counterparty = beneficiary.name
      } else {
        try {
          assertValidPixKey(body.pixKeyType!, body.pixKey!)
        } catch {
          return HttpResponse.json(
            error('INVALID_PIX_KEY', 'Chave PIX inválida para o tipo informado.', requestCorrelationId),
            { status: 400 },
          )
        }
        pixKey = body.pixKey
        pixKeyType = body.pixKeyType
        counterparty = body.pixKey!
      }

      const now = new Date()
      const nowIso = now.toISOString()
      const scheduledFor =
        typeof body.scheduledFor === 'string' && body.scheduledFor.length > 0
          ? body.scheduledFor
          : undefined
      if (scheduledFor && Number.isNaN(new Date(scheduledFor).getTime())) {
        return HttpResponse.json(
          error('VALIDATION_ERROR', 'scheduledFor deve ser uma data/hora válida.', requestCorrelationId),
          { status: 400 },
        )
      }
      const isScheduled = Boolean(scheduledFor)

      if (!isScheduled) {
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
        if (db.dailySpentCents + body.amountCents > db.dailyLimitCents) {
          return HttpResponse.json(
            error(
              'DAILY_LIMIT_EXCEEDED',
              'Limite diário de PIX excedido para essa transferência.',
              requestCorrelationId,
            ),
            { status: 409 },
          )
        }
      }

      const transfer: Transfer = {
        id: crypto.randomUUID(),
        ...(beneficiaryId ? { beneficiaryId } : {}),
        ...(pixKey ? { pixKey } : {}),
        ...(pixKeyType ? { pixKeyType } : {}),
        amountCents: body.amountCents,
        status: isScheduled ? 'SCHEDULED' : 'COMPLETED',
        createdAt: nowIso,
        ...(scheduledFor ? { scheduledFor } : {}),
        endToEndId: `E${crypto.randomUUID().replace(/-/g, '').slice(0, 32)}`,
        correlationId: requestCorrelationId,
      }

      db.transfers.push(transfer)

      if (!isScheduled) {
        db.availableCents -= body.amountCents
        db.dailySpentCents += body.amountCents
        db.transactions.unshift({
          id: crypto.randomUUID(),
          type: 'PIX_OUT',
          amountCents: body.amountCents,
          description: `PIX para ${counterparty}`,
          createdAt: nowIso,
          counterparty,
        })
        markOnboardingStep(db.onboarding, 'FIRST_PIX')
        db.notifications.unshift({
          id: crypto.randomUUID(),
          title: 'PIX enviado',
          body: `Transferência de ${body.amountCents} centavos para ${counterparty} foi concluída.`,
          read: false,
          createdAt: nowIso,
        })
      }

      if (idempotencyKey) {
        db.idempotency.set(idempotencyKey, transfer)
      }

      return HttpResponse.json(transfer, { status: 201 })
    }),
    http.get(endpoint(apiBasePath, '/transfers/pix/qr-payload'), ({ request }) => {
      const url = new URL(request.url)
      const amountCents = Number.parseInt(url.searchParams.get('amountCents') ?? '', 10)
      const pixKey = url.searchParams.get('pixKey')?.trim() ?? ''
      const requestCorrelationId = request.headers.get('X-Correlation-Id') ?? correlationId()
      if (!Number.isInteger(amountCents) || amountCents <= 0 || !pixKey) {
        return HttpResponse.json(
          error(
            'VALIDATION_ERROR',
            'amountCents e pixKey são obrigatórios e amountCents deve ser positivo.',
            requestCorrelationId,
          ),
          { status: 400 },
        )
      }
      return HttpResponse.json({ payload: buildQrPayload(amountCents, pixKey) })
    }),
    http.get(endpoint(apiBasePath, '/transfers/:id'), ({ params }) => {
      const transfer = db.transfers.find((item) => item.id === params.id)
      if (!transfer) {
        return HttpResponse.json(
          error('TRANSFER_NOT_FOUND', 'Transferência não encontrada.'),
          { status: 404 },
        )
      }
      return HttpResponse.json(transfer)
    }),
    http.get(endpoint(apiBasePath, '/notifications'), () =>
      HttpResponse.json({ items: db.notifications }),
    ),
    http.post(endpoint(apiBasePath, '/notifications/read-all'), () => {
      for (const notification of db.notifications) {
        notification.read = true
      }
      return new HttpResponse(null, { status: 204 })
    }),
    http.post(endpoint(apiBasePath, '/notifications/:id/read'), ({ params }) => {
      const notification = db.notifications.find((item) => item.id === params.id)
      if (!notification) {
        return HttpResponse.json(
          error('NOTIFICATION_NOT_FOUND', 'Notificação não encontrada.'),
          { status: 404 },
        )
      }
      notification.read = true
      return new HttpResponse(null, { status: 204 })
    }),
  ]
}
