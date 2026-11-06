import { before, describe, it, mock } from 'node:test'
import assert from 'node:assert/strict'
import request from 'supertest'
import type { Express } from 'express'
import config from 'config'
import { createTestApp } from './helpers/setup'
import { register, login } from './helpers/auth'
import { ProductModel } from '../../models/product'
import * as db from '../../data/mongodb'

let app: Express
let selected: number
let other: number
let token: string
before(async () => {
  assert.ok(['localhost', '127.0.0.1', '[::1]'].includes(new URL(config.get<string>('application.chatBot.llmApiUrl')).hostname), 'Tests require the local test-model endpoint')
  app = (await createTestApp()).app
  const a = await ProductModel.create({ name: 'TCC selected juice', description: 'Fixture juice', price: 2, deluxePrice: 1 })
  const b = await ProductModel.create({ name: 'TCC other juice', description: 'Other fixture', price: 3, deluxePrice: 2 })
  selected = a.id
  other = b.id
  await db.reviewsCollection.insert({ _id: 'tcc-review-first', product: selected, message: 'First normal review', author: 'first@example.test' })
  await db.reviewsCollection.insert({ _id: 'tcc-review-second', product: selected, message: 'Second normal review', author: 'second@example.test' })
  await db.reviewsCollection.insert({ _id: 'tcc-review-unrelated', product: other, message: 'Unrelated review', author: 'other@example.test' })
  const credentials = { email: 'tcc-chat@example.test', password: 'coverage-password' }
  await register(app, credentials)
  token = (await login(app, credentials)).token
}, { timeout: 60000 })

function stream (deltas: object[], finish = 'stop') {
  const chunks = [...deltas.map(delta => ({ choices: [{ index: 0, delta, finish_reason: null }] })),
    { choices: [{ index: 0, delta: {}, finish_reason: finish }] }]
  return new Response(chunks.map(c => `data: ${JSON.stringify(c)}\n\n`).join('') + 'data: [DONE]\n\n', {
    status: 200, headers: { 'Content-Type': 'text/event-stream' }
  })
}

async function runTool (name: string, args: object, authenticated = false) {
  const requests: any[] = []
  let result: any
  const transport = mock.method(globalThis, 'fetch', async (_url: any, init: any) => {
    assert.equal(init.method, 'POST')
    const body = JSON.parse(String(init.body))
    requests.push(body)
    if (requests.length === 1) {
      return stream([{ tool_calls: [{ index: 0, id: 'tcc-call', type: 'function', function: { name, arguments: JSON.stringify(args) } }] }], 'tool_calls')
    }
    assert.equal(requests.length, 2, 'Unexpected extra model request')
    const message = body.messages.find((m: any) => m.role === 'tool')
    assert.ok(message, 'Tool output must reach the model transport')
    assert.equal(message.tool_call_id, 'tcc-call')
    result = JSON.parse(message.content)
    return stream([{ content: 'TCC simulated answer.' }])
  })
  try {
    let query = request(app).post('/rest/chat').send({ messages: [{ role: 'user', content: 'TCC normal request' }] })
    if (authenticated) query = query.set('Authorization', `Bearer ${token}`)
    const response = await query
    assert.equal(response.status, 200)
    assert.match(response.headers['content-type'], /text\/event-stream/)
    assert.match(response.headers['cache-control'], /no-cache/)
    assert.ok(response.text.includes('TCC simulated answer.'))
    assert.ok(response.text.includes('data: [DONE]'))
    const frames = response.text.split('\n').filter(line => line.startsWith('data: ') && !line.includes('[DONE]'))
      .map(line => JSON.parse(line.slice(6)))
    assert.ok(frames.some(frame => frame.choices?.[0]?.delta?.tool_calls?.[0]?.function?.name === name))
    assert.ok(frames.some(frame => frame.choices?.[0]?.finish_reason === 'stop'))
    assert.equal(requests.length, 2)
    return { result, firstRequest: requests[0] }
  } finally { transport.mock.restore() }
}

void describe('TCC chat tool and SSE contracts', () => {
  void it('returns exactly the matching persisted reviews through the tool round trip', async () => {
    const { result, firstRequest } = await runTool('getProductReviews', { id: String(selected) })
    assert.deepEqual(result.map((r: any) => ({ id: r._id, message: r.message, product: r.product })).sort((a: any, b: any) => a.id.localeCompare(b.id)), [
      { id: 'tcc-review-first', message: 'First normal review', product: selected },
      { id: 'tcc-review-second', message: 'Second normal review', product: selected }
    ])
    assert.equal(firstRequest.messages[0].role, 'system')
    const definition = firstRequest.tools.find((t: any) => t.function.name === 'getProductReviews')
    assert.ok(definition)
    assert.equal(definition.function.parameters.properties.id.type, 'string')
  })

  void it('returns an empty review list for an unknown numeric product', async () => {
    assert.deepEqual((await runTool('getProductReviews', { id: '987654321' })).result, [])
  })

  void it('keeps reviews for a different product separate', async () => {
    const { result } = await runTool('getProductReviews', { id: String(other) })
    assert.deepEqual(result.map((r: any) => r._id), ['tcc-review-unrelated'])
  })

  void it('normalizes a numeric string with leading zeroes before selecting reviews', async () => {
    const { result } = await runTool('getProductReviews', { id: '00' + String(selected) })
    assert.deepEqual(result.map((r: any) => r._id).sort(), ['tcc-review-first', 'tcc-review-second'])
  })

  void it('keeps the product search tool functional', async () => {
    const { result } = await runTool('searchProducts', { query: 'TCC selected juice' })
    assert.equal(result.length, 1)
    assert.equal(result[0].id, selected)
    assert.equal(result[0].name, 'TCC selected juice')
    assert.equal(result[0].price, 2)
  })

  void it('reports an unauthenticated order lookup through the tool', async () => {
    assert.equal((await runTool('getOrderById', { orderId: 'tcc-order' })).result.error, 'Customer not authenticated')
  })

  void it('returns an owned order and rejects a different customer order', async () => {
    await db.ordersCollection.insert({ orderId: 'tcc-owned', email: 'tcc-ch*t@*x*mpl*.t*st', totalPrice: 2 })
    await db.ordersCollection.insert({ orderId: 'tcc-foreign', email: 'someone-else', totalPrice: 3 })
    const owned = (await runTool('getOrderById', { orderId: 'tcc-owned' }, true)).result
    assert.equal(owned.orderId, 'tcc-owned')
    assert.equal(owned.totalPrice, 2)
    assert.equal((await runTool('getOrderById', { orderId: 'tcc-foreign' }, true)).result.error, 'Order does not belong to the current customer')
  })

  void it('keeps normal coupon generation functional', async () => {
    const { result } = await runTool('generateCoupon', { discount: 10 })
    assert.equal(result.discount, 10)
    assert.equal(typeof result.couponCode, 'string')
    assert.ok(result.couponCode.length > 0)
  })

  void it('finishes an SSE error response when the simulated provider fails', async () => {
    const transport = mock.method(globalThis, 'fetch', async () => new Response('{"error":{"message":"TCC simulated provider failure"}}', {
      status: 400, headers: { 'Content-Type': 'application/json' }
    }))
    try {
      const response = await request(app).post('/rest/chat').send({ messages: [{ role: 'user', content: 'TCC error fixture' }] })
      assert.equal(response.status, 200)
      assert.ok(response.text.includes('error'))
      assert.ok(response.text.includes('data: [DONE]'))
    } finally { transport.mock.restore() }
  })
})
