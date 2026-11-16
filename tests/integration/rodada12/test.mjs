/** Node 24.14.0. Integracao local reduzida: Express/Finale/SQLite reais;
 * rotas/modelos extraidos do commit fixado. Identidade, hash e hooks simulados.
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
const depsDir = process.env.ROUND12_DEPS
assert.ok(wt && depsDir, 'Defina JUICE_SHOP_WORKTREE e ROUND12_DEPS')
const meta = JSON.parse(readFileSync(new URL('../../../outputs/sast_antes/catalogo_meta.json', import.meta.url)))
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: wt, encoding: 'utf8' }).trim(), meta.commit_alvo)
assert.equal(execFileSync('git', ['status', '--porcelain'], { cwd: wt, encoding: 'utf8' }).trim(), '')
const require = createRequire(path.join(depsDir, 'package.json'))
const versions = { express: '4.22.1', 'finale-rest': '1.2.2', sequelize: '6.37.3', sqlite3: '5.1.7', clarinet: '0.12.6' }
for (const [name, version] of Object.entries(versions)) assert.equal(require(`${name}/package.json`).version, version)
const express = require('express')
const finale = require('finale-rest')
const { Sequelize, Model, DataTypes } = require('sequelize')
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
for (const init of [UserModelInit, FeedbackModelInit, CaptchaModelInit]) init(sequelize)

test('rodada 12: integracao local e controles', { timeout: 30000 }, async t => {
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
      if (req.path === '/api/Users' && (!req.body.email?.trim() || !req.body.password?.trim() || req.body.password !== req.body.passwordRepeat)) return res.sendStatus(400)
      if (req.path === '/api/Feedbacks' && (!Number.isInteger(req.body.rating) || req.body.rating < 1 || req.body.rating > 5)) return res.sendStatus(400)
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
    await t.test('email e senha vazios sem confirmacao persistem; controle bloqueia', async () => {
      const payload = { email: '', password: '' }
      const result = await post('/api/Users', payload)
      assert.equal(result.status, 201, result.body)
      const user = await UserModel.findOne({ where: { email: '' } })
      assert.ok(user)
      assert.equal(user.password, security.hash(''))
      const before = await UserModel.count()
      assert.equal((await post('/api/Users', payload, true)).status, 400)
      assert.equal(await UserModel.count(), before)
    })
    await t.test('confirmacao divergente persiste; controle bloqueia e permite igualdade', async () => {
      const result = await post('/api/Users', { email: 'mismatch@example.test', password: 'one', passwordRepeat: 'two' })
      assert.equal(result.status, 201, result.body)
      assert.ok(await UserModel.findOne({ where: { email: 'mismatch@example.test' } }))
      assert.equal((await post('/api/Users', { email: 'blocked@example.test', password: 'one', passwordRepeat: 'two' }, true)).status, 400)
      assert.equal(await UserModel.count({ where: { email: 'blocked@example.test' } }), 0)
      assert.equal((await post('/api/Users', { email: 'valid@example.test', password: 'one', passwordRepeat: 'one' }, true)).status, 201)
    })
    await CaptchaModel.create({ captchaId: 1, captcha: '1+1', answer: '2' })
    await t.test('zero estrelas persiste com CAPTCHA valido; controles verificam intervalo', async () => {
      const payload = { comment: 'zero', rating: 0, captchaId: 1, captcha: '2' }
      const result = await post('/api/Feedbacks', payload)
      assert.equal(result.status, 201, result.body)
      assert.equal((await FeedbackModel.findOne({ where: { comment: 'zero' } })).rating, 0)
      assert.equal((await post('/api/Feedbacks', { ...payload, comment: 'blocked' }, true)).status, 400)
      assert.equal(await FeedbackModel.count({ where: { comment: 'blocked' } }), 0)
      assert.equal((await post('/api/Feedbacks', { ...payload, rating: 3, comment: 'valid' }, true)).status, 201)
      assert.equal((await post('/api/Feedbacks', { ...payload, captcha: 'wrong', comment: 'bad-captcha' })).status, 401)
    })
  } finally {
    await new Promise(resolve => listener.close(resolve))
    await sequelize.close()
  }
})
