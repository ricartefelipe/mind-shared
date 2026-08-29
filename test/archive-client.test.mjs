import test from 'node:test'
import assert from 'node:assert/strict'
import { assertSafeId } from '../dist/archive/client.js'

test('assertSafeId aceita slug e rejeita path traversal', () => {
  assert.equal(assertSafeId('atlas-norte'), 'atlas-norte')
  assert.throws(() => assertSafeId('../etc/passwd'))
  assert.throws(() => assertSafeId('a/b'))
})
