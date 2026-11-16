import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import * as security from '../../lib/insecurity'

void describe('TCC shared security contracts', () => {
  void it('preserves authenticated token roundtrip', () => {
    const user = { data: { id: 42, email: 'coverage@example.test' } }
    const token = security.authorize(user)
    assert.equal(security.verify(token), true)
    assert.deepEqual(security.decode(token).data, user.data)
  })
  void it('preserves deterministic distinct digests without pinning a secret', () => {
    assert.equal(security.hash('one'), security.hash('one'))
    assert.notEqual(security.hash('one'), security.hash('two'))
    assert.equal(security.hmac('one'), security.hmac('one'))
    assert.notEqual(security.hmac('one'), security.hmac('two'))
  })
  void it('preserves coupon amount roundtrip and approved redirect', () => {
    assert.equal(security.discountFromCoupon(security.generateCoupon(10)), 10)
    assert.equal(security.isRedirectAllowed('https://github.com/juice-shop/juice-shop'), true)
  })
  void it('preserves deluxe tokens as deterministic user specific values', () => {
    const a = security.deluxeToken('one@example.test')
    assert.equal(typeof a, 'string')
    assert.ok(a.length > 0)
    assert.equal(a, security.deluxeToken('one@example.test'))
    assert.notEqual(a, security.deluxeToken('two@example.test'))
  })
})
