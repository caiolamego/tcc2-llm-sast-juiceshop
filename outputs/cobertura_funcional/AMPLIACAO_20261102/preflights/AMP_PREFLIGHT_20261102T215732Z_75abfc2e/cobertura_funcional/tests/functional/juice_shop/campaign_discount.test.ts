import { before, describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import request from 'supertest'
import type { Express } from 'express'
import { createTestApp } from './helpers/setup'
import { register, login } from './helpers/auth'
import { BasketModel } from '../../models/basket'
import { BasketItemModel } from '../../models/basketitem'
import { ProductModel } from '../../models/product'
import * as db from '../../data/mongodb'

let app: Express
let token: string
let userId: number
before(async () => {
  app = (await createTestApp()).app
  const credentials = { email: 'tcc-campaign@example.test', password: 'coverage-password' }
  const created = await register(app, credentials)
  userId = created.body.data.id
  token = (await login(app, credentials)).token
}, { timeout: 60000 })

const validOn = Date.parse('2019-03-07T23:00:00Z')
const scenarios: Array<[string, string | undefined, number]> = [
  ['applies the campaign discount to the persisted order total', `WMNSDY2019-${validOn}`, 75],
  ['does not discount a campaign with a mismatched date', `WMNSDY2019-${validOn + 86400000}`, 0],
  ['does not discount an unknown campaign', `TCC_UNKNOWN-${validOn}`, 0],
  ['preserves the normal total without campaign data', undefined, 0]
]

void describe('TCC campaign discount contracts', () => {
  for (const [name, campaign, discount] of scenarios) {
    void it(name, async (context) => {
      // Only Date is controlled; HTTP, streams and database timers remain real.
      context.mock.timers.enable({ apis: ['Date'], now: validOn })
      const basket = await BasketModel.create({ UserId: userId, coupon: null })
      const product = await ProductModel.findByPk(1)
      assert.ok(product)
      await BasketItemModel.create({ BasketId: basket.id, ProductId: product.id, quantity: 2 })
      const subtotal = product.price * 2
      const promotionalAmount = (subtotal * discount / 100).toFixed(2)
      let orderId: string | undefined
      try {
        const response = await request(app).post(`/rest/basket/${basket.id}/checkout`)
          .set('Authorization', `Bearer ${token}`)
          .send(campaign === undefined ? {} : { couponData: Buffer.from(campaign).toString('base64') })
        assert.equal(response.status, 200)
        orderId = response.body.orderConfirmation
        assert.equal(typeof orderId, 'string')
        const order = await db.ordersCollection.findOne({ orderId })
        assert.ok(order)
        assert.equal(Number(order.promotionalAmount), Number(promotionalAmount))
        assert.equal(order.totalPrice, subtotal - Number(promotionalAmount))
        assert.equal(order.deliveryPrice, 0)
        assert.equal(order.products.length, 1)
        assert.equal(order.products[0].quantity, 2)
        assert.equal(order.products[0].total, subtotal)
        assert.equal(await BasketItemModel.count({ where: { BasketId: basket.id } }), 0)
        assert.equal((await basket.reload()).coupon, null)
      } finally {
        context.mock.timers.reset()
        if (orderId && /^[a-zA-Z0-9-]+$/.test(orderId)) {
          await fs.rm(path.join('ftp', `order_${orderId}.pdf`), { force: true })
        }
        await BasketItemModel.destroy({ where: { BasketId: basket.id } })
        await basket.destroy()
      }
    })
  }
})
