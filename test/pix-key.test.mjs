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

test('CPF aceita 11 dígitos com dígitos verificadores válidos', () => {
  assert.doesNotThrow(() => assertValidPixKey('CPF', '52998224725'))
})

test('CPF rejeita dígito verificador errado e dígitos repetidos', () => {
  for (const key of ['52998224724', '12345678901', '11111111111']) {
    assert.throws(
      () => assertValidPixKey('CPF', key),
      (error) => error instanceof Error && error.message.includes('INVALID_PIX_KEY'),
      key,
    )
  }
})

test('CNPJ aceita numérico e alfanumérico com dígitos verificadores válidos', () => {
  assert.doesNotThrow(() => assertValidPixKey('CNPJ', '11222333000181'))
  // Exemplo publicado pela Receita Federal para o CNPJ alfanumérico.
  assert.doesNotThrow(() => assertValidPixKey('CNPJ', '12ABC34501DE35'))
})

test('CNPJ rejeita dígito errado, máscara, minúsculas e repetidos', () => {
  for (const key of ['11222333000182', '11.222.333/0001-81', '12abc34501de35', '00000000000000', '1122233300018']) {
    assert.throws(
      () => assertValidPixKey('CNPJ', key),
      (error) => error instanceof Error && error.message.includes('INVALID_PIX_KEY'),
      key,
    )
  }
})

test('CNPJ não passa como CPF nem como chave aleatória', () => {
  assert.throws(() => assertValidPixKey('CPF', '11222333000181'))
  assert.throws(() => assertValidPixKey('RANDOM', '11222333000181'))
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

test('RANDOM aceita UUID com ou sem hífens', () => {
  assert.doesNotThrow(() =>
    assertValidPixKey('RANDOM', 'a1b2c3d4e5f6789012345678abcdef01'),
  )
  assert.doesNotThrow(() =>
    assertValidPixKey('RANDOM', '123e4567-e89b-12d3-a456-426614174000'),
  )
  assert.throws(() => assertValidPixKey('RANDOM', '123e4567-e89b12d3a456426614174000'))
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
