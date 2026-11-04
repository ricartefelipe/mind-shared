import assert from 'node:assert/strict'
import test from 'node:test'
import { setupServer } from 'msw/node'
import { createMindHandlers } from '../dist/msw.js'

function createServer(options = {}) {
  const server = setupServer(...createMindHandlers(options))
  server.listen({ onUnhandledRequest: 'error' })
  return server
}

async function getBalance() {
  const response = await fetch('http://mind.local/api/v1/wallet/balance')
  assert.equal(response.status, 200)
  return response.json()
}

test('PIX retorna INSUFFICIENT_FUNDS quando o saldo não cobre', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const response = await fetch('http://mind.local/api/v1/transfers/pix', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      beneficiaryId: 'b1',
      amountCents: 300_000,
    }),
  })

  assert.equal(response.status, 409)
  const body = await response.json()
  assert.equal(body.code, 'INSUFFICIENT_FUNDS')
  assert.equal(typeof body.message, 'string')
  assert.equal(typeof body.correlationId, 'string')

  const balance = await getBalance()
  assert.equal(balance.availableCents, 250_000)
  assert.equal(balance.dailySpentCents, 0)
})

test('PIX retorna DAILY_LIMIT_EXCEEDED quando ultrapassa o limite diário', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const response = await fetch('http://mind.local/api/v1/transfers/pix', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      beneficiaryId: 'b1',
      amountCents: 100_001,
    }),
  })

  assert.equal(response.status, 409)
  const body = await response.json()
  assert.equal(body.code, 'DAILY_LIMIT_EXCEEDED')
  assert.equal(typeof body.correlationId, 'string')

  const balance = await getBalance()
  assert.equal(balance.availableCents, 250_000)
  assert.equal(balance.dailySpentCents, 0)
})

test('retry com mesma Idempotency-Key devolve a mesma transferência sem debitar de novo', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const payload = {
    beneficiaryId: 'b1',
    amountCents: 10_000,
  }
  const headers = {
    'Content-Type': 'application/json',
    'Idempotency-Key': 'idem-pix-1',
  }

  const first = await fetch('http://mind.local/api/v1/transfers/pix', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  assert.equal(first.status, 201)
  const firstBody = await first.json()
  assert.equal(firstBody.status, 'COMPLETED')
  assert.equal(firstBody.amountCents, 10_000)
  assert.ok(firstBody.endToEndId)
  assert.ok(firstBody.correlationId)

  const second = await fetch('http://mind.local/api/v1/transfers/pix', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })
  assert.equal(second.status, 201)
  const secondBody = await second.json()
  assert.deepEqual(secondBody, firstBody)

  const balance = await getBalance()
  assert.equal(balance.availableCents, 240_000)
  assert.equal(balance.dailySpentCents, 10_000)
})

test('PIX agendado não debita até o GET de balance processar o vencimento', async (t) => {
  let agora = new Date('2026-11-04T12:00:00Z')
  const server = createServer({ now: () => agora })
  t.after(() => server.close())

  const future = new Date(agora.getTime() + 60 * 60 * 1000).toISOString()
  const createFuture = await fetch('http://mind.local/api/v1/transfers/pix', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      beneficiaryId: 'b1',
      amountCents: 20_000,
      scheduledFor: future,
    }),
  })
  assert.equal(createFuture.status, 201)
  const futureTransfer = await createFuture.json()
  assert.equal(futureTransfer.status, 'SCHEDULED')
  assert.equal(futureTransfer.scheduledFor, future)

  let balance = await getBalance()
  assert.equal(balance.availableCents, 250_000)
  assert.equal(balance.dailySpentCents, 0)

  // Com fuso: o vencimento compara instantes, não o texto da data.
  const emCincoMinutos = '2026-11-04T09:05:00-03:00'
  const createSoon = await fetch('http://mind.local/api/v1/transfers/pix', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pixKey: 'destino@email.com',
      pixKeyType: 'EMAIL',
      amountCents: 15_000,
      scheduledFor: emCincoMinutos,
    }),
  })
  assert.equal(createSoon.status, 201)
  const pastTransfer = await createSoon.json()
  assert.equal(pastTransfer.status, 'SCHEDULED')
  assert.equal(pastTransfer.beneficiaryId, undefined)

  balance = await getBalance()
  assert.equal(balance.availableCents, 250_000)

  agora = new Date(agora.getTime() + 10 * 60 * 1000)
  balance = await getBalance()
  assert.equal(balance.availableCents, 235_000)
  assert.equal(balance.dailySpentCents, 15_000)

  const fetched = await fetch(`http://mind.local/api/v1/transfers/${pastTransfer.id}`)
  assert.equal(fetched.status, 200)
  const fetchedBody = await fetched.json()
  assert.equal(fetchedBody.status, 'COMPLETED')
  assert.equal(fetchedBody.id, pastTransfer.id)
})

test('notifications read-all marca todas como lidas', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const listBefore = await fetch('http://mind.local/api/v1/notifications')
  assert.equal(listBefore.status, 200)
  const beforeBody = await listBefore.json()
  assert.ok(beforeBody.items.length >= 2)
  assert.ok(beforeBody.items.every((item) => item.read === false))

  const markOne = await fetch(`http://mind.local/api/v1/notifications/${beforeBody.items[0].id}/read`, {
    method: 'POST',
  })
  assert.equal(markOne.status, 204)

  const readAll = await fetch('http://mind.local/api/v1/notifications/read-all', {
    method: 'POST',
  })
  assert.equal(readAll.status, 204)

  const listAfter = await fetch('http://mind.local/api/v1/notifications')
  const afterBody = await listAfter.json()
  assert.ok(afterBody.items.every((item) => item.read === true))
})

test('onboarding completa login + favorecido + PIX + extrato', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const login = await fetch('http://mind.local/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'demo@vuemind.dev',
      password: 'demo123',
    }),
  })
  assert.equal(login.status, 200)

  let onboarding = await (await fetch('http://mind.local/api/v1/me/onboarding')).json()
  assert.equal(onboarding.steps.find((step) => step.id === 'PROFILE_OK').done, true)
  assert.equal(onboarding.completed, false)

  const beneficiaryResponse = await fetch('http://mind.local/api/v1/beneficiaries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: 'Novo Favorecido',
      pixKey: 'novo@email.com',
      pixKeyType: 'EMAIL',
    }),
  })
  assert.equal(beneficiaryResponse.status, 201)
  const beneficiaryBody = await beneficiaryResponse.json()

  onboarding = await (await fetch('http://mind.local/api/v1/me/onboarding')).json()
  assert.equal(onboarding.steps.find((step) => step.id === 'FIRST_BENEFICIARY').done, true)

  const pixResponse = await fetch('http://mind.local/api/v1/transfers/pix', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      beneficiaryId: beneficiaryBody.id,
      amountCents: 1_000,
    }),
  })
  assert.equal(pixResponse.status, 201)
  assert.equal((await pixResponse.json()).status, 'COMPLETED')

  onboarding = await (await fetch('http://mind.local/api/v1/me/onboarding')).json()
  assert.equal(onboarding.steps.find((step) => step.id === 'FIRST_PIX').done, true)

  const statement = await fetch('http://mind.local/api/v1/wallet/transactions')
  assert.equal(statement.status, 200)

  onboarding = await (await fetch('http://mind.local/api/v1/me/onboarding')).json()
  assert.equal(onboarding.steps.find((step) => step.id === 'VIEW_STATEMENT').done, true)
  assert.equal(onboarding.completed, true)
})

test('qr-payload devolve payload determinístico', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const response = await fetch(
    'http://mind.local/api/v1/transfers/pix/qr-payload?amountCents=1500&pixKey=ana%40email.com',
  )
  assert.equal(response.status, 200)
  assert.deepEqual(await response.json(), {
    payload: 'MINDPIX|v1|ana@email.com|1500',
  })
})

test('PIX agendado no passado ou além de 365 dias responde 400', async (t) => {
  const agora = new Date('2026-11-04T12:00:00Z')
  const server = createServer({ now: () => agora })
  t.after(() => server.close())

  const agendar = (scheduledFor) =>
    fetch('http://mind.local/api/v1/transfers/pix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ beneficiaryId: 'b1', amountCents: 1_000, scheduledFor }),
    })

  const noPassado = await agendar(new Date(agora.getTime() - 60_000).toISOString())
  assert.equal(noPassado.status, 400)
  assert.equal((await noPassado.json()).code, 'SCHEDULE_IN_PAST')

  const agoraMesmo = await agendar(agora.toISOString())
  assert.equal(agoraMesmo.status, 400)
  assert.equal((await agoraMesmo.json()).code, 'SCHEDULE_IN_PAST')

  const umAno = 365 * 24 * 60 * 60 * 1000
  const longe = await agendar(new Date(agora.getTime() + umAno + 1_000).toISOString())
  assert.equal(longe.status, 400)
  assert.equal((await longe.json()).code, 'SCHEDULE_TOO_FAR')

  const noLimite = await agendar(new Date(agora.getTime() + umAno).toISOString())
  assert.equal(noLimite.status, 201)
  assert.equal((await noLimite.json()).status, 'SCHEDULED')
})

test('favorecido de demonstração Mercado Central tem chave CNPJ', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const response = await fetch('http://mind.local/api/v1/beneficiaries')
  const { items } = await response.json()
  const mercado = items.find((b) => b.id === 'b2')
  assert.equal(mercado.pixKeyType, 'CNPJ')
  assert.equal(mercado.pixKey, '11222333000181')
})
