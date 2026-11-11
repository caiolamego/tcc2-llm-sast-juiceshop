import { before, describe, it, mock } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import request from 'supertest'
import type { Express } from 'express'
import { createTestApp } from './helpers/setup'
import { login, register } from './helpers/auth'
import { UserModel } from '../../models/user'
import { WalletModel } from '../../models/wallet'
import { BasketItemModel } from '../../models/basketitem'
import { ProductModel } from '../../models/product'
import { FeedbackModel } from '../../models/feedback'
import { ComplaintModel } from '../../models/complaint'
import { RecycleModel } from '../../models/recycle'
import { SecurityQuestionModel } from '../../models/securityQuestion'
import { SecurityAnswerModel } from '../../models/securityAnswer'
import { AddressModel } from '../../models/address'
import { PrivacyRequestModel } from '../../models/privacyRequests'
import { CardModel } from '../../models/card'
import { QuantityModel } from '../../models/quantity'
import { ChallengeModel } from '../../models/challenge'
import { ChallengeDependencyModel } from '../../models/challengeDependency'
import { HintModel } from '../../models/hint'

let app: Express
let authorization: string
let userId: number
let basketId: number
before(async () => {
  app = (await createTestApp()).app
  const credentials = { email: 'tcc-generated-resources@example.test', password: 'coverage-password' }
  const response = await register(app, credentials)
  userId = response.body.data.id
  const auth = await login(app, credentials)
  authorization = `Bearer ${auth.token}`
  basketId = auth.bid
}, { timeout: 60000 })

function authenticated (req: request.Test) { return req.set('Authorization', authorization) }
function success (response: request.Response, status = 200) {
  assert.equal(response.status, status)
  assert.match(response.headers['content-type'], /application\/json/)
  assert.equal(response.body.status, 'success')
  assert.ok(response.body.data !== undefined)
  return response.body.data
}

void describe('TCC generated server resource contracts', () => {
  void it('creates exactly one wallet for a normally registered user', async () => {
    const wallets = await WalletModel.findAll({ where: { UserId: userId } })
    assert.equal(wallets.length, 1)
    assert.equal(Number(wallets[0].balance), 0)
  })

  void it('logs a wallet creation failure while completing normal registration', async () => {
    const cause = new Error('TCC wallet persistence failure')
    const create = mock.method(WalletModel, 'create', async () => { throw cause })
    const log = mock.method(console, 'log', () => {})
    try {
      const response = await register(app, { email: 'tcc-wallet-failure@example.test', password: 'coverage-password' })
      assert.equal(response.status, 201)
      assert.equal((await UserModel.findByPk(response.body.data.id))?.email, 'tcc-wallet-failure@example.test')
      assert.equal(create.mock.callCount(), 1)
      assert.equal(log.mock.calls.filter(call => call.arguments[0] === cause).length, 1)
    } finally {
      create.mock.restore()
      log.mock.restore()
    }
  })

  void it('returns users without password or TOTP secrets and without default pagination', async () => {
    const users = success(await authenticated(request(app).get('/api/Users')))
    assert.ok(Array.isArray(users))
    assert.equal(users.length, await UserModel.count())
    assert.ok(users.some((u: any) => u.id === userId))
    for (const user of users) {
      assert.equal(Object.hasOwn(user, 'password'), false)
      assert.equal(Object.hasOwn(user, 'totpSecret'), false)
    }
  })

  void it('creates reads and updates a product through its generated endpoints', async () => {
    const created = success(await authenticated(request(app).post('/api/Products'))
      .send({ name: 'TCC normal product', description: 'Normal test product', price: 12.5, deluxePrice: 10 }), 201)
    const persisted = await ProductModel.findByPk(created.id)
    assert.ok(persisted)
    assert.equal(persisted.name, 'TCC normal product')
    assert.equal(persisted.price, 12.5)
    success(await authenticated(request(app).put(`/api/Products/${created.id}`)).send({ price: 13.5 }))
    const read = success(await request(app).get(`/api/Products/${created.id}`))
    assert.equal(read.price, 13.5)
    assert.equal((await persisted.reload()).price, 13.5)
    assert.equal((await authenticated(request(app).delete(`/api/Products/${created.id}`))).status, 401)
  })

  void it('persists and lists normal feedback through the generated resource', async () => {
    const captcha = (await request(app).get('/rest/captcha')).body
    const created = success(await request(app).post('/api/Feedbacks').send({
      comment: 'TCC resource feedback', rating: 4, captchaId: captcha.captchaId, captcha: captcha.answer
    }), 201)
    const persisted = await FeedbackModel.findByPk(created.id)
    assert.ok(persisted)
    assert.equal(persisted.comment, 'TCC resource feedback')
    assert.equal(persisted.rating, 4)
    assert.ok(success(await request(app).get('/api/Feedbacks')).some((r: any) => r.id === created.id))
    assert.equal((await authenticated(request(app).put(`/api/Feedbacks/${created.id}`)).send({ rating: 2 })).status, 401)
    assert.equal((await persisted.reload()).rating, 4)
  })

  void it('creates reads updates and deletes an owned basket item', async () => {
    const created = success(await authenticated(request(app).post('/api/BasketItems'))
      .send({ BasketId: basketId, ProductId: 1, quantity: 1 }))
    const id = created.id
    assert.equal((await BasketItemModel.findByPk(id))?.quantity, 1)
    assert.equal(success(await authenticated(request(app).get(`/api/BasketItems/${id}`))).BasketId, basketId)
    success(await authenticated(request(app).put(`/api/BasketItems/${id}`)).send({ quantity: 2 }))
    assert.equal((await BasketItemModel.findByPk(id))?.quantity, 2)
    success(await authenticated(request(app).delete(`/api/BasketItems/${id}`)))
    assert.equal(await BasketItemModel.findByPk(id), null)
  })

  void it('lists challenges with their actual dependency association', async () => {
    const challenge = await ChallengeModel.findOne()
    assert.ok(challenge)
    const dependency = await ChallengeDependencyModel.create({
      ChallengeId: challenge.id, name: 'TCC dependency', key: 'tcc-normal-dependency',
      documentation: 'https://example.test/documentation', missing: false
    })
    try {
      const list = success(await request(app).get('/api/Challenges'))
      assert.equal(list.length, await ChallengeModel.count())
      const found = list.find((c: any) => c.id === challenge.id)
      assert.ok(found)
      assert.ok(Array.isArray(found.ChallengeDependencies))
      assert.ok(found.ChallengeDependencies.some((d: any) => d.id === dependency.id && d.name === dependency.name))
    } finally { await dependency.destroy() }
  })

  void it('persists and lists an authenticated complaint', async () => {
    const data = success(await authenticated(request(app).post('/api/Complaints'))
      .send({ UserId: userId, message: 'TCC normal complaint' }), 201)
    assert.equal((await ComplaintModel.findByPk(data.id))?.message, 'TCC normal complaint')
    const list = success(await authenticated(request(app).get('/api/Complaints')))
    assert.ok(list.some((c: any) => c.id === data.id && c.message === 'TCC normal complaint'))
    assert.equal((await authenticated(request(app).get(`/api/Complaints/${data.id}`))).status, 401)
  })

  void it('persists and retrieves a normal recycling request', async () => {
    const data = success(await authenticated(request(app).post('/api/Recycles'))
      .send({ UserId: userId, AddressId: 1, quantity: 3, isPickup: true, date: '2030-01-02' }), 201)
    const persisted = await RecycleModel.findByPk(data.id)
    assert.ok(persisted)
    assert.equal(persisted.quantity, 3)
    assert.equal(persisted.isPickup, true)
    const list = success(await request(app).get(`/api/Recycles/${data.id}`))
    assert.ok(list.some((r: any) => r.id === data.id && r.quantity === 3))
    assert.equal((await authenticated(request(app).put(`/api/Recycles/${data.id}`)).send({ quantity: 9 })).status, 401)
  })

  void it('lists all security questions and persists a security answer for the new user', async () => {
    const questions = success(await request(app).get('/api/SecurityQuestions'))
    assert.equal(questions.length, await SecurityQuestionModel.count())
    assert.ok(questions.length > 0)
    const created = success(await authenticated(request(app).post('/api/SecurityAnswers'))
      .send({ UserId: userId, SecurityQuestionId: questions[0].id, answer: 'TCC normal answer' }), 201)
    const persisted = await SecurityAnswerModel.findByPk(created.id)
    assert.ok(persisted)
    assert.equal(persisted.UserId, userId)
    assert.equal(persisted.SecurityQuestionId, questions[0].id)
    assert.ok(persisted.answer.length > 0)
    assert.notEqual(persisted.answer, 'TCC normal answer')
    assert.equal((await authenticated(request(app).get('/api/SecurityAnswers'))).status, 401)
  })

  void it('creates reads updates and deletes an owned address', async () => {
    const created = success(await authenticated(request(app).post('/api/Addresss')).send({
      fullName: 'TCC Customer', mobileNum: '9800000000', zipCode: 'NX 101',
      streetAddress: 'Test Street', city: 'Test City', state: 'DF', country: 'Brazil'
    }), 201)
    assert.equal((await AddressModel.findByPk(created.id))?.UserId, userId)
    assert.equal(success(await authenticated(request(app).get(`/api/Addresss/${created.id}`))).city, 'Test City')
    success(await authenticated(request(app).put(`/api/Addresss/${created.id}`)).send({ city: 'Updated City' }))
    assert.equal((await AddressModel.findByPk(created.id))?.city, 'Updated City')
    success(await authenticated(request(app).delete(`/api/Addresss/${created.id}`)))
    assert.equal(await AddressModel.findByPk(created.id), null)
  })

  void it('persists a privacy request and keeps its list endpoint restricted', async () => {
    const created = success(await authenticated(request(app).post('/api/PrivacyRequests'))
      .send({ UserId: userId, deletionRequested: true }), 201)
    const persisted = await PrivacyRequestModel.findByPk(created.id)
    assert.ok(persisted)
    assert.equal(persisted.UserId, userId)
    assert.equal(persisted.deletionRequested, true)
    assert.equal((await authenticated(request(app).get('/api/PrivacyRequests'))).status, 401)
  })

  void it('creates lists and deletes an owned payment card', async () => {
    const created = success(await authenticated(request(app).post('/api/Cards'))
      .send({ fullName: 'TCC Customer', cardNum: 1234567887654321, expMonth: 6, expYear: 2085 }), 201)
    const persisted = await CardModel.findByPk(created.id)
    assert.ok(persisted)
    assert.equal(persisted.UserId, userId)
    assert.equal(persisted.expMonth, 6)
    const list = success(await authenticated(request(app).get('/api/Cards')))
    assert.ok(list.some((c: any) => c.id === created.id && c.cardNum === '************4321'))
    success(await authenticated(request(app).delete(`/api/Cards/${created.id}`)))
    assert.equal(await CardModel.findByPk(created.id), null)
  })

  void it('lists persisted stock quantities without default pagination', async () => {
    const list = success(await authenticated(request(app).get('/api/Quantitys')))
    assert.equal(list.length, await QuantityModel.count())
    assert.ok(list.length > 0)
    const first = await QuantityModel.findByPk(list[0].id)
    assert.ok(first)
    assert.equal(list[0].quantity, first.quantity)
  })

  void it('lists hints and persists an allowed hint update', async () => {
    const list = success(await request(app).get('/api/Hints'))
    assert.equal(list.length, await HintModel.count())
    assert.ok(list.length > 0)
    const hint = await HintModel.findByPk(list[0].id)
    assert.ok(hint)
    success(await request(app).put(`/api/Hints/${hint.id}`).send({ unlocked: !hint.unlocked }))
    assert.equal((await HintModel.findByPk(hint.id))?.unlocked, !hint.unlocked)
  })

  const translations = [
    ['Product', ProductModel, 'name', '/api/Products', true],
    ['ProductDescription', ProductModel, 'description', '/api/Products', true],
    ['Challenge', ChallengeModel, 'description', '/api/Challenges', false],
    ['SecurityQuestion', SecurityQuestionModel, 'question', '/api/SecurityQuestions', false],
    ['Hint', HintModel, 'text', '/api/Hints', false]
  ] as const
  for (const [name, model, field, endpoint, readable] of translations) {
    void it(`translates the ${name} response through its generated hook`, async () => {
      const dictionary = JSON.parse(fs.readFileSync('i18n/de_DE.json', 'utf8'))
      const originalText = 'Apple Juice (1000ml)'
      const translated = dictionary[originalText]
      assert.ok(translated && translated !== originalText)
      const row: any = await (model as any).findOne()
      assert.ok(row)
      const original = row[field]
      await row.update({ [field]: originalText })
      try {
        const list = success(await request(app).get(endpoint).set('Cookie', 'language=de_DE'))
        assert.equal(list.find((entry: any) => entry.id === row.id)[field], translated)
        if (readable) {
          const read = success(await request(app).get(`${endpoint}/${row.id}`).set('Cookie', 'language=de_DE'))
          assert.equal(read[field], translated)
        }
      } finally { await row.update({ [field]: original }) }
    })
  }

  void it('translates challenge descriptions separately from their warning suffix', async () => {
    const dictionary = JSON.parse(fs.readFileSync('i18n/de_DE.json', 'utf8'))
    const label = 'Apple Juice (1000ml)'
    const warning = ' <em>(This challenge is <strong>potentially harmful</strong> on Windows!)</em>'
    const row = await ChallengeModel.findOne()
    assert.ok(row)
    const original = row.description
    await row.update({ description: label + warning })
    try {
      const list = success(await request(app).get('/api/Challenges').set('Cookie', 'language=de_DE'))
      assert.equal(list.find((c: any) => c.id === row.id).description, dictionary[label] + dictionary[warning])
    } finally { await row.update({ description: original }) }
  })
})
