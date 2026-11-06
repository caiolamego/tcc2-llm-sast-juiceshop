import { before, describe, it, mock } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import request from 'supertest'
import type { Express } from 'express'
import { createTestApp } from './helpers/setup'
import { register, login } from './helpers/auth'
import { UserModel } from '../../models/user'
import * as db from '../../data/mongodb'

// Each contract holds with or without the vulnerability: it replaces the legitimate
// part of a target test that also demanded the vulnerability (conjunto D, v3).
let app: Express
let token: string
let userId: number
const credentials = { email: 'tcc-legitimate@example.test', password: 'coverage-password' }
const image = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64')

before(async () => {
  app = (await createTestApp()).app
  userId = (await register(app, credentials)).body.data.id
  token = (await login(app, credentials)).token
}, { timeout: 60000 })

void describe('TCC legitimate behaviour contracts', () => {
  void it('lets the author edit their own review', async () => {
    const authorization = { Authorization: `Bearer ${token}` }
    const original = `TCC review ${userId}`
    const created = await request(app).put('/rest/products/1/reviews').set(authorization)
      .send({ message: original, author: credentials.email })
    assert.equal(created.status, 201)
    const review = await db.reviewsCollection.findOne({ message: original })
    assert.ok(review)
    const edited = await request(app).patch('/rest/products/reviews').set(authorization)
      .send({ id: review._id, message: 'TCC edited review' })
    assert.equal(edited.status, 200)
    const stored = await db.reviewsCollection.findOne({ _id: review._id })
    assert.equal(stored.message, 'TCC edited review')
  })

  void it('answers an error without a location to a redirect without target', async () => {
    const response = await request(app).get('/redirect').redirects(0)
    assert.ok(response.status >= 400)
    assert.equal(response.headers.location, undefined)
  })

  void it('stores the image of a public URL as the profile image', async () => {
    // Only the outbound request is simulated: the address is public and needs no name lookup.
    const download = mock.method(globalThis, 'fetch', async () => new Response(image, { status: 200 }))
    let file: string | undefined
    try {
      const response = await request(app).post('/profile/image/url').set('Cookie', `token=${token}`)
        .field('imageUrl', 'https://93.184.216.34/tcc-profile.png').redirects(0)
      assert.equal(response.status, 302)
      const user = await UserModel.findByPk(userId)
      assert.ok(user?.profileImage.startsWith('/assets/public/images/uploads/'))
      file = `frontend/dist/frontend${user.profileImage}`
      assert.deepEqual(fs.readFileSync(file), image)
    } finally {
      download.mock.restore()
      if (file) fs.rmSync(file, { force: true })
    }
  })
})
