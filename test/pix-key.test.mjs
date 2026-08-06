import assert from 'node:assert/strict'
import test from 'node:test'
import { assertValidPixKey } from '../dist/pixKey.js'
import { buildQrPayload } from '../dist/qrPayload.js'

test('EMAIL aceita endereço válido', () => {
  assert.doesNotThrow(() => assertValidPixKey('EMAIL', 'user@example.com'))
})

test('EMAIL rejeita endereço inválido', () => {
  assert.throws(
    () => assertValidPixKey('EMAIL', 'not-an-email'),
    (error) => error instanceof Error && error.message.includes('INVALID_PIX_KEY'),
  )
})

test('CPF aceita 11 dígitos', () => {
  assert.doesNotThrow(() => assertValidPixKey('CPF', '12345678901'))
})

test('CPF rejeita formato inválido', () => {
  assert.throws(
    () => assertValidPixKey('CPF', '1234567890'),
    (error) => error instanceof Error && error.message.includes('INVALID_PIX_KEY'),
  )
})

test('PHONE aceita com ou sem +', () => {
  assert.doesNotThrow(() => assertValidPixKey('PHONE', '+5511999998888'))
  assert.doesNotThrow(() => assertValidPixKey('PHONE', '11999998888'))
})

test('PHONE rejeita formato inválido', () => {
  assert.throws(
    () => assertValidPixKey('PHONE', '123'),
    (error) => error instanceof Error && error.message.includes('INVALID_PIX_KEY'),
  )
})

test('RANDOM aceita 32 hex', () => {
  assert.doesNotThrow(() =>
    assertValidPixKey('RANDOM', 'a1b2c3d4e5f6789012345678abcdef01'),
  )
})

test('RANDOM rejeita formato inválido', () => {
  assert.throws(
    () => assertValidPixKey('RANDOM', 'not-a-random-key'),
    (error) => error instanceof Error && error.message.includes('INVALID_PIX_KEY'),
  )
})

test('buildQrPayload retorna string determinística', () => {
  assert.equal(buildQrPayload(1500, 'user@example.com'), 'MINDPIX|v1|user@example.com|1500')
})
