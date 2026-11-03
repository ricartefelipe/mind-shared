import assert from 'node:assert/strict'
import test from 'node:test'
import { setupServer } from 'msw/node'
import { createEndToEndId, DEMO_ISPB, END_TO_END_ID_PATTERN } from '../dist/endToEndId.js'
import { createMindHandlers } from '../dist/msw.js'

function createServer() {
  const server = setupServer(...createMindHandlers())
  server.listen({ onUnhandledRequest: 'error' })
  return server
}

function pix(body, headers = {}) {
  return fetch('http://mind.local/api/v1/transfers/pix', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  })
}

test('createEndToEndId segue o formato do arranjo PIX, com ISPB fictício e data e hora UTC', () => {
  const id = createEndToEndId(new Date('2026-11-03T23:59:41Z'))

  assert.equal(id.length, 32)
  assert.match(id, END_TO_END_ID_PATTERN)
  assert.ok(id.startsWith(`E${DEMO_ISPB}202611032359`))
  assert.ok(createEndToEndId(new Date('2027-01-01T00:00:00Z')).startsWith('E99999999202701010000'))
})

test('createEndToEndId não repete em milhares de chamadas no mesmo minuto', () => {
  const date = new Date('2026-11-03T12:00:00Z')
  const ids = new Set(Array.from({ length: 5000 }, () => createEndToEndId(date)))
  assert.equal(ids.size, 5000)
})

test('o padrão recusa o formato antigo e outros fora do arranjo', () => {
  assert.equal(END_TO_END_ID_PATTERN.test('E0123456789abcdef0123456789abcdef'), false)
  assert.equal(END_TO_END_ID_PATTERN.test('E99999999202613032359abcdefghijk'), false)
  assert.equal(END_TO_END_ID_PATTERN.test('E99999999202611032359abcdefghij-'), false)
})

test('PIX imediato devolve end-to-end no formato; repetir com a mesma chave mantém o código', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const headers = { 'Idempotency-Key': 'e2e-idem' }
  const first = await (await pix({ beneficiaryId: 'b1', amountCents: 1_000 }, headers)).json()
  const again = await (await pix({ beneficiaryId: 'b1', amountCents: 1_000 }, headers)).json()
  const other = await (await pix({ beneficiaryId: 'b1', amountCents: 1_000 })).json()

  assert.match(first.endToEndId, END_TO_END_ID_PATTERN)
  assert.equal(again.endToEndId, first.endToEndId)
  assert.notEqual(other.endToEndId, first.endToEndId)
})

test('PIX agendado só recebe o end-to-end quando é executado', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const past = new Date(Date.now() - 60_000).toISOString()
  const created = await (await pix({ beneficiaryId: 'b1', amountCents: 2_000, scheduledFor: past })).json()
  assert.equal(created.status, 'SCHEDULED')
  assert.equal(created.endToEndId, undefined)

  await fetch('http://mind.local/api/v1/wallet/balance')

  const executed = await (await fetch(`http://mind.local/api/v1/transfers/${created.id}`)).json()
  assert.equal(executed.status, 'COMPLETED')
  assert.match(executed.endToEndId, END_TO_END_ID_PATTERN)
})
