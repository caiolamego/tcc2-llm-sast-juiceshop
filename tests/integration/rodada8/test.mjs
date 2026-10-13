/** Node 24.14.0. Integracao local reduzida: Express/Finale/SQLite reais;
 * rotas/modelos extraidos do commit fixado. Identidade, hooks e PDF simulados.
 * Nao altera o alvo, nao usa servidor externo nem executa LLM.
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire, stripTypeScriptTypes } from 'node:module'
import { once } from 'node:events'
import path from 'node:path'
import { test } from 'node:test'

const wt = process.env.JUICE_SHOP_WORKTREE
const depsDir = process.env.ROUND8_DEPS
assert.ok(wt && depsDir, 'Defina JUICE_SHOP_WORKTREE e ROUND8_DEPS')
const meta = JSON.parse(readFileSync(new URL('../../../outputs/sast_antes/catalogo_meta.json', import.meta.url)))
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: wt, encoding: 'utf8' }).trim(), meta.commit_alvo)
assert.equal(execFileSync('git', ['status', '--porcelain'], { cwd: wt, encoding: 'utf8' }).trim(), '')
const require = createRequire(path.join(depsDir, 'package.json'))
const versions = { express: '4.22.1', 'finale-rest': '1.2.2', sequelize: '6.37.3', sqlite3: '5.1.7', clarinet: '0.12.6' }
for (const [name, version] of Object.entries(versions)) assert.equal(require(`${name}/package.json`).version, version)
const express = require('express')
const finale = require('finale-rest')
const { Sequelize, Model, DataTypes } = require('sequelize')
const clarinet = require('clarinet')
const read = file => readFileSync(path.join(wt, file), 'utf8')
function segment(source, first, last) {
  const start = source.indexOf(first)
  const end = source.indexOf(last, start + first.length)
  assert.ok(start >= 0 && end > start, `Ancora ausente: ${first}`)
  return source.slice(start, end)
}
function evaluate(source, result, dependencies) {
  const js = stripTypeScriptTypes(source)
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\s*$/gm, '')
    .replace(/^export \{[^}]*\}\s*;?/gm, '')
    .replace(/^export /gm, '')
  return new Function(...Object.keys(dependencies), `${js}\nreturn (${result});`)(...Object.values(dependencies))
}
const challenges = new Proxy({}, { get: (_, key) => key })
const challengeUtils = { solveIf() {}, notSolved: () => false }
const principal = { data: { id: 1, email: 'alice@example.test' }, bid: 1 }
const security = {
  authenticatedUsers: { from: () => principal, get: () => principal },
  roles: { admin: 'admin', customer: 'customer' },
  hash: value => `hash-${value}`, sanitizeSecure: value => value,
  sanitizeLegacy: value => value, sanitizeHtml: value => value,
  isDeluxe: () => false, discountFromCoupon: () => undefined
}
const utils = { isChallengeEnabled: () => false, contains: (a, b) => a.includes(b),
  asyncHandler: handler => (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next),
  randomHexString: () => 'fixed' }
const config = { get: () => 'local-test' }
const common = { Model, DataTypes, security, utils, config, challenges, challengeUtils }
const sequelize = new Sequelize({ dialect: 'sqlite', storage: ':memory:', logging: false, dialectModule: require('sqlite3') })
const { UserModel, UserModelInit } = evaluate(read('models/user.ts'), '{UserModel: User, UserModelInit}', common)
const { FeedbackModel, FeedbackModelInit } = evaluate(read('models/feedback.ts'), '{FeedbackModel: Feedback, FeedbackModelInit}', common)
const { CaptchaModel, CaptchaModelInit } = evaluate(read('models/captcha.ts'), '{CaptchaModel: Captcha, CaptchaModelInit}', common)
const { BasketItemModel, BasketItemModelInit } = evaluate(read('models/basketitem.ts'), '{BasketItemModel: BasketItem, BasketItemModelInit}', common)
for (const init of [UserModelInit, FeedbackModelInit, CaptchaModelInit, BasketItemModelInit]) init(sequelize)

test('rodada 8: integracao local e controles', { timeout: 30000 }, async t => {
  await sequelize.sync({ force: true }) // Somente SQLite :memory: deste teste.
  const serverSource = read('server.ts')
  const verifySource = segment(read('routes/verify.ts'), 'export const emptyUserRegistration', 'export const accessControlChallenges')
  const verify = evaluate(verifySource, '{emptyUserRegistration, forgedFeedbackChallenge, captchaBypassChallenge, registerAdminChallenge, passwordRepeatChallenge}', common)
  const { verifyCaptcha } = evaluate(read('routes/captcha.ts'), '{verifyCaptcha}', { CaptchaModel })
  const app = express()
  app.use(express.json({ verify: (req, res, buffer) => { req.rawBody = buffer.toString() } }))
  app.use((req, res, next) => { req.__ = res.__ = text => text; next() })
  // Controle protegido opcional do harness; nunca e aplicado ao checkout.
  app.use((req, res, next) => {
    if (req.get('x-test-protected') === 'yes') {
      if (req.path === '/api/Users') req.body.role = 'customer'
      if (req.path === '/api/Feedbacks') req.body.UserId = principal.data.id
      if (req.path === '/api/BasketItems' && (!Number.isInteger(req.body.quantity) || req.body.quantity <= 0)) return res.sendStatus(400)
    }
    next()
  })
  // Trecho literal com middlewares de feedback e cadastro, em sua ordem real.
  evaluate(segment(serverSource, "app.post('/api/Feedbacks', verify.forgedFeedbackChallenge())", '/* Unauthorized users are not allowed to access B2B API */'), 'undefined', { app, verify, verifyCaptcha, utils })
  finale.initialize({ app, sequelize })
  const declaration = segment(serverSource, 'const autoModels = [', '\n  for (const { name, exclude, model, include } of autoModels)')
  const descriptorLine = name => {
    const line = declaration.split('\n').find(line => line.includes(`name: '${name}'`))
    assert.ok(line)
    return evaluate(`const entry = ${line.trim().replace(/,$/, '')}`, 'entry', { UserModel, FeedbackModel })
  }
  // Mesma chamada resource do servidor; apenas os dois modelos em escopo.
  const resourceSource = segment(serverSource, 'const resource = finale.resource({', '// create a wallet when a new user is registered using API')
  const walletHook = segment(serverSource, "if (name === 'User') { // vuln-code-snippet", '// vuln-code-snippet end registerAdminChallenge')
  const WalletModel = { create: async () => ({}) }
  for (const name of ['User', 'Feedback']) {
    const descriptor = descriptorLine(name)
    const resource = evaluate(resourceSource, 'resource', { finale, ...descriptor, include: undefined })
    evaluate(walletHook, 'undefined', { name, resource, WalletModel })
  }
  const parseSource = segment(read('lib/utils.ts'), 'export const parseJsonCustom', 'export const toSimpleIpAddress')
  const parseJsonCustom = evaluate(parseSource, 'parseJsonCustom', { clarinet })
  const QuantityModel = { findOne: async () => ({ quantity: 100, limitPerUser: 5 }), update: async () => {} }
  const basket = evaluate(read('routes/basketItems.ts'), '{quantityCheckBeforeBasketItemAddition, addBasketItem}',
    { ...common, utils: { ...utils, parseJsonCustom }, BasketItemModel, QuantityModel })
  app.post('/api/BasketItems', basket.quantityCheckBeforeBasketItemAddition(), utils.asyncHandler(basket.addBasketItem()))
  app.use((err, req, res, next) => res.status(500).json({ error: String(err) }))
  const listener = app.listen(0, '127.0.0.1')
  await once(listener, 'listening')
  const origin = `http://127.0.0.1:${listener.address().port}`
  const post = async (route, body, protectedMode = false) => {
    const response = await fetch(origin + route, { method: 'POST', headers: {
      'content-type': 'application/json', ...(protectedMode ? { 'x-test-protected': 'yes' } : {})
    }, body: JSON.stringify(body) })
    return { status: response.status, body: await response.text() }
  }
  try {
    await t.test('cadastro anonimo persiste role admin; controle impoe customer', async () => {
      for (const protectedMode of [false, true]) {
        const email = protectedMode ? 'protected@example.test' : 'unprotected@example.test'
        const result = await post('/api/Users', { email, password: 'test', passwordRepeat: 'test', role: 'admin' }, protectedMode)
        assert.equal(result.status, 201, result.body)
        const user = await UserModel.findOne({ where: { email } })
        assert.equal(user.role, protectedMode ? 'customer' : 'admin')
      }
    })
    await CaptchaModel.create({ captchaId: 1, captcha: '1+1', answer: '2' })
    await t.test('feedback aceita outro UserId; controle impoe identidade da sessao', async () => {
      for (const protectedMode of [false, true]) {
        const comment = protectedMode ? 'protected' : 'unprotected'
        const result = await post('/api/Feedbacks', { UserId: 2, comment, rating: 3, captchaId: 1, captcha: '2' }, protectedMode)
        assert.equal(result.status, 201, result.body)
        const feedback = await FeedbackModel.findOne({ where: { comment } })
        assert.equal(feedback.UserId, protectedMode ? 1 : 2)
      }
      const invalid = await post('/api/Feedbacks', { UserId: 2, comment: 'invalid-captcha', rating: 3, captchaId: 1, captcha: 'wrong' })
      assert.equal(invalid.status, 401, invalid.body)
    })
    await t.test('quantidade negativa atravessa validacao e persiste; controle bloqueia', async () => {
      const result = await post('/api/BasketItems', { BasketId: 1, ProductId: 1, quantity: -2 })
      assert.equal(result.status, 200, result.body)
      const item = await BasketItemModel.findOne({ where: { BasketId: 1, ProductId: 1 } })
      assert.equal(item.quantity, -2)
      const denied = await post('/api/BasketItems', { BasketId: 1, ProductId: 2, quantity: -2 }, true)
      assert.equal(denied.status, 400)
      assert.equal(await BasketItemModel.count({ where: { ProductId: 2 } }), 0)
      const normal = await post('/api/BasketItems', { BasketId: 1, ProductId: 3, quantity: 2 }, true)
      assert.equal(normal.status, 200, normal.body)
    })
    await t.test('checkout real calcula total negativo e debito negativo', async () => {
      const item = await BasketItemModel.findOne({ where: { ProductId: 1 } })
      let savedOrder, debit, finish
      const writer = { on: (event, callback) => { finish = callback } }
      class PDFDocument {
        pipe() { return writer }
        font() { return this } fontSize() { return this } text() { return this }
        moveTo() { return this } lineTo() { return this } stroke() { return this } moveDown() { return this }
        end() { finish() }
      }
      const orderSource = read('routes/order.ts')
      assert.ok(orderSource.includes("await import('pdfkit')"))
      const factory = evaluate(orderSource.replace("await import('pdfkit')", '({default: TestPDFDocument})'), 'placeOrder', {
        ...common, TestPDFDocument: PDFDocument, path, fs: { createWriteStream: () => writer },
        products: { christmasSpecial: { id: -1 } }, ProductModel: {}, DeliveryModel: {}, QuantityModel,
        BasketItemModel, BasketModel: { findOne: async () => ({ coupon: null, update: async () => {}, Products: [{ id: 1, name: 'item', price: 10, deluxePrice: 10, BasketItem: item }] }) },
        WalletModel: { findOne: async () => ({ balance: 100 }), decrement: async change => { debit = change.balance }, increment: async () => {} },
        db: { ordersCollection: { insert: async order => { savedOrder = order } } }
      })
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Checkout nao concluiu')), 3000)
        factory()({ params: { id: 1 }, body: { UserId: 1, orderDetails: { paymentId: 'wallet' } }, __: text => text },
          { json: () => { clearTimeout(timeout); resolve() } }, error => { clearTimeout(timeout); reject(error) })
      })
      assert.equal(savedOrder.totalPrice, -20)
      assert.equal(debit, -20)
    })
    await t.test('emails distintos cadastraveis colidem e exportam pedido alheio', async () => {
      for (const email of ['alice@example.test', 'elice@example.test']) {
        const result = await post('/api/Users', { email, password: 'test', passwordRepeat: 'test' })
        assert.equal(result.status, 201, result.body)
      }
      const ownerEmail = 'elice@example.test'
      principal.data.id = (await UserModel.findOne({ where: { email: principal.data.email } })).id
      const ownerId = (await UserModel.findOne({ where: { email: ownerEmail } })).id
      assert.notEqual(ownerEmail, principal.data.email)
      assert.equal(ownerEmail.replace(/[aeiou]/gi, '*'), principal.data.email.replace(/[aeiou]/gi, '*'))
      const stored = { ownerId, email: ownerEmail.replace(/[aeiou]/gi, '*'), orderId: 'foreign', totalPrice: 20, products: [], bonus: 0, eta: '1' }
      for (const protectedMode of [false, true]) {
        const db = { ordersCollection: { find: async filter =>
          stored.email === filter.email && (!protectedMode || stored.ownerId === principal.data.id) ? [stored] : [] },
        reviewsCollection: { find: async () => [] } }
        const factory = evaluate(read('routes/dataExport.ts'), 'dataExport', {
          ...common, db, MemoryModel: { findAll: async () => [] }
        })
        let result
        await factory()({ headers: { authorization: 'Bearer simulated' }, body: { UserId: 1 } },
          { status() { return this }, send(value) { result = value } }, error => { throw error })
        const orders = JSON.parse(result.userData).orders
        assert.equal(orders.length, protectedMode ? 0 : 1)
        if (!protectedMode) assert.equal(orders[0].orderId, 'foreign')
      }
    })
  } finally {
    await new Promise(resolve => listener.close(resolve))
    await sequelize.close()
  }
})
