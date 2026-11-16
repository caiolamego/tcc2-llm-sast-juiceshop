import { describe, it, before } from 'node:test'
import assert from 'node:assert/strict'
import request from 'supertest'
import type { Express } from 'express'
import { createTestApp } from './helpers/setup'
import { register, login } from './helpers/auth'

let app: Express
before(async () => { app = (await createTestApp()).app }, { timeout: 60000 })

void describe('TCC review likes contracts', () => {
  void it('increments the selected review once and rejects the same user twice', async () => {
    const credentials = { email: 'tcc-coverage-likes@example.test', password: 'coverage-password' }
    await register(app, credentials)
    const { token } = await login(app, credentials)
    const reviews = await request(app).get('/rest/products/1/reviews')
    assert.equal(reviews.status, 200)
    const original = reviews.body.data[0]
    const first = await request(app).post('/rest/products/reviews')
      .set('Authorization', `Bearer ${token}`).send({ id: original._id })
    assert.equal(first.status, 200)
    const updated = await request(app).get('/rest/products/1/reviews')
    const review = updated.body.data.find((r: any) => r._id === original._id)
    assert.equal(review.likesCount, original.likesCount + 1)
    assert.equal(review.likedBy.filter((email: string) => email === credentials.email).length, 1)
    const second = await request(app).post('/rest/products/reviews')
      .set('Authorization', `Bearer ${token}`).send({ id: original._id })
    assert.equal(second.status, 403)
    const final = await request(app).get('/rest/products/1/reviews')
    assert.equal(final.body.data.find((r: any) => r._id === original._id).likesCount, review.likesCount)
  })
})
