import assert from 'node:assert/strict'
import test from 'node:test'
import { setupServer } from 'msw/node'
import { createMindHandlers } from '../dist/msw.js'

function createServer() {
  const server = setupServer(...createMindHandlers())
  server.listen({ onUnhandledRequest: 'error' })
  return server
}

test('provisiona um usuário TotalRecall e permite o login', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  const provisionResponse = await fetch('http://mind.local/internal/v1/totalrecall/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'totalrecall-user@vuemind.dev',
      name: 'Usuário TotalRecall',
      password: 'senha-segura',
      action: 'upsert',
    }),
  })

  assert.equal(provisionResponse.status, 200)
  assert.deepEqual(await provisionResponse.json(), {
    id: 'totalrecall-user@vuemind.dev',
    email: 'totalrecall-user@vuemind.dev',
    name: 'Usuário TotalRecall',
    enabled: true,
  })

  const loginResponse = await fetch('http://mind.local/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'totalrecall-user@vuemind.dev',
      password: 'senha-segura',
    }),
  })

  assert.equal(loginResponse.status, 200)
  assert.equal((await loginResponse.json()).user.email, 'totalrecall-user@vuemind.dev')
})

test('disable impede o login de usuário provisionado', async (t) => {
  const server = createServer()
  t.after(() => server.close())

  await fetch('http://mind.local/internal/v1/totalrecall/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'disabled-user@vuemind.dev',
      name: 'Usuário Desabilitado',
      password: 'senha-segura',
    }),
  })

  const disableResponse = await fetch('http://mind.local/internal/v1/totalrecall/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'disabled-user@vuemind.dev',
      action: 'disable',
    }),
  })

  assert.equal(disableResponse.status, 200)
  assert.equal((await disableResponse.json()).enabled, false)

  const loginResponse = await fetch('http://mind.local/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'disabled-user@vuemind.dev',
      password: 'senha-segura',
    }),
  })

  assert.equal(loginResponse.status, 401)
})
