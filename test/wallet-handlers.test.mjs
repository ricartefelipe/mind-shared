import assert from 'node:assert/strict'
import test from 'node:test'
import { setupServer } from 'msw/node'
import { createMindHandlers } from '../dist/msw.js'

function createServer() {
  const server = setupServer(...createMindHandlers())
  server.listen({ onUnhandledRequest: 'error' })
  return server
}

test('balance inclui campos de limite e bloqueio', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const response = await fetch('http://mind.local/api/v1/wallet/balance')
  assert.equal(response.status, 200)
  const body = await response.json()
  assert.equal(body.availableCents, 250_000)
  assert.equal(body.blockedCents, 10_000)
  assert.equal(body.dailyLimitCents, 100_000)
  assert.equal(body.dailySpentCents, 0)
  assert.equal(body.currency, 'BRL')
})

test('transactions retorna paginação page/pageSize/total', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const response = await fetch('http://mind.local/api/v1/wallet/transactions?page=1&pageSize=2')
  assert.equal(response.status, 200)
  const body = await response.json()
  assert.equal(body.page, 1)
  assert.equal(body.pageSize, 2)
  assert.equal(body.total, 5)
  assert.equal(body.items.length, 2)

  const page2 = await fetch('http://mind.local/api/v1/wallet/transactions?page=2&pageSize=2')
  const page2Body = await page2.json()
  assert.equal(page2Body.page, 2)
  assert.equal(page2Body.pageSize, 2)
  assert.equal(page2Body.total, 5)
  assert.equal(page2Body.items.length, 2)
  assert.notEqual(page2Body.items[0].id, body.items[0].id)
})

test('transactions filtra por q em description e counterparty', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const byDescription = await fetch('http://mind.local/api/v1/wallet/transactions?q=mercado')
  assert.equal(byDescription.status, 200)
  const descriptionBody = await byDescription.json()
  assert.equal(descriptionBody.total, 1)
  assert.equal(descriptionBody.items[0].description, 'Pagamento mercado')

  const byCounterparty = await fetch('http://mind.local/api/v1/wallet/transactions?q=carlos')
  const counterpartyBody = await byCounterparty.json()
  assert.equal(counterpartyBody.total, 1)
  assert.equal(counterpartyBody.items[0].counterparty, 'Carlos')
})

test('primeiro GET de transactions marca VIEW_STATEMENT no onboarding', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const before = await fetch('http://mind.local/api/v1/me/onboarding')
  assert.equal(before.status, 200)
  const beforeBody = await before.json()
  const viewBefore = beforeBody.steps.find((step) => step.id === 'VIEW_STATEMENT')
  assert.equal(viewBefore.done, false)

  const statement = await fetch('http://mind.local/api/v1/wallet/transactions')
  assert.equal(statement.status, 200)

  const after = await fetch('http://mind.local/api/v1/me/onboarding')
  const afterBody = await after.json()
  const viewAfter = afterBody.steps.find((step) => step.id === 'VIEW_STATEMENT')
  assert.equal(viewAfter.done, true)
  assert.equal(afterBody.completed, false)
})
