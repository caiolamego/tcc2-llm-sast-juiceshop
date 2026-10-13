/** Integracao reduzida local: motores Express/Finale/SQLite/hbs reais.
 * Nenhuma alteracao no alvo. Sessao de data erasure e modelos auxiliares simulados.
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire, stripTypeScriptTypes } from 'node:module'
import { once } from 'node:events'
import path from 'node:path'
import { test } from 'node:test'

const wt = process.env.JUICE_SHOP_WORKTREE
const deps = process.env.ROUND9_DEPS
assert.ok(wt && deps, 'Defina JUICE_SHOP_WORKTREE e ROUND9_DEPS')
const read = p => readFileSync(path.join(wt, p), 'utf8')
const meta = JSON.parse(readFileSync(new URL('../../../outputs/sast_antes/catalogo_meta.json', import.meta.url)))
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: wt, encoding: 'utf8' }).trim(), meta.commit_alvo)
assert.equal(execFileSync('git', ['status', '--porcelain'], { cwd: wt, encoding: 'utf8' }).trim(), '')
const require = createRequire(path.join(deps, 'package.json'))
for (const [name, version] of Object.entries({ express: '4.22.1', 'finale-rest': '1.2.2', sequelize: '6.37.3', sqlite3: '5.1.7', hbs: '4.2.0', 'express-jwt': '0.1.3' })) {
  assert.equal(require(`${name}/package.json`).version, version)
}
const express = require('express')
const finale = require('finale-rest')
const { Sequelize, Model, DataTypes } = require('sequelize')
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
    .replace(/^export default [^\n]+/gm, '')
    .replace(/^export /gm, '')
  return new Function(...Object.keys(dependencies), `${js}\nreturn (${result});`)(...Object.values(dependencies))
}
const source = read('server.ts')
const challengeUtils = { solveIf() {}, notSolved: () => false }
const challenges = new Proxy({}, { get: (_, key) => key })
const utils = { isChallengeEnabled: () => false, extractFilename: path.basename, jwtFrom: () => undefined }
const insecurity = read('lib/insecurity.ts')
const authDeclarations = insecurity.split('\n').filter(line => /^export const (isAuthorized|denyAll) =/.test(line)).join('\n')
const security = evaluate(authDeclarations, '{isAuthorized, denyAll}', { expressJwt: require('express-jwt'), publicKey: 'local-test-only' })
security.sanitizeSecure = value => value
const common = { Model, DataTypes, utils, security, challengeUtils, challenges }

test('rodada 9: integracao local com controles', { timeout: 30000 }, async t => {
  const sequelize = new Sequelize({ dialect: 'sqlite', storage: ':memory:', logging: false, dialectModule: require('sqlite3') })
  t.after(() => sequelize.close())
  const { ProductModel, ProductModelInit } = evaluate(read('models/product.ts'), '{ProductModel: Product, ProductModelInit}', common)
  ProductModelInit(sequelize)
  await sequelize.sync({ force: true }) // Exclusivamente SQLite em memoria.
  const product = await ProductModel.create({ name: 'Local test', description: 'Original', price: 10, deluxePrice: 8, image: 'test.png' })
  const app = express()
  app.use(express.json())
  app.use((req, res, next) => { req.cookies = {}; req.__ = res.__ = s => s; next() })
  // Middleware global real: ausencia de token nao bloqueia requisicao.
  const updateAuth = evaluate(segment(insecurity, 'export const updateAuthenticatedUsers', '\n}').concat('\n}'), 'updateAuthenticatedUsers', {
    utils, authenticatedUsers: { get: () => undefined }, publicKey: 'local-test-only',
    jwt: { verify() { throw new Error('Teste anonimo nao deveria verificar JWT') } }
  })
  const verifyJwt = evaluate(segment(read('routes/verify.ts'), 'export const jwtChallenges', 'export const serverSideChallenges'), 'jwtChallenges', { challengeUtils, challenges, utils })
  app.use(verifyJwt())
  app.use(updateAuth())
  // Controle opcional do teste, nao aplicado ao alvo.
  app.put('/api/Products/:id', (req, res, next) => req.get('x-test-protected') === 'yes' ? security.denyAll()(req, res, next) : next())
  evaluate(segment(source, '/* Products: Only GET', '/* Challenges: GET'), 'undefined', { app, security })
  finale.initialize({ app, sequelize })
  const descriptor = source.split('\n').find(line => line.includes("name: 'Product',"))
  assert.ok(descriptor)
  const entry = evaluate(`const entry = ${descriptor.trim().replace(/,$/, '')}`, 'entry', { ProductModel })
  const resource = evaluate(segment(source, 'const resource = finale.resource({', '// create a wallet'), 'resource', { finale, ...entry, include: undefined })
  evaluate(segment(source, "if (name === 'Product') {", '// fix the api difference'), 'undefined', { name: 'Product', resource })
  const sendHook = segment(source, 'resource.all.send.before(', '\n  }')
  evaluate(sendHook, 'undefined', { resource })

  app.engine('hbs', require('hbs').__express)
  app.set('view engine', 'hbs')
  app.set('views', path.join(wt, 'views'))
  const erasureSecurity = { authenticatedUsers: { get: token => token === 'test-session' ? { data: { id: 1, email: 'local@example.test' } } : undefined } }
  const router = evaluate(read('routes/dataErasure.ts'), 'router', {
    express, path, utils, challengeUtils, challenges, security: erasureSecurity,
    config: { get: () => 'local-test' }, themes: { 'bluegrey-lightgreen': {} },
    Entities: class { encode(value) { return value } },
    PrivacyRequestModel: { create: async () => ({}) },
    SecurityQuestionModel: {}, SecurityAnswerModel: {}, UserModel: {}
  })
  app.use('/dataerasure', (req, res, next) => {
    // Sessao de teste explicitamente simulada; nao testa login/cookies do navegador.
    if (req.get('x-test-session') === 'yes') req.cookies.token = 'test-session'
    if (req.get('x-test-protected') === 'yes') req.body = { email: req.body.email, securityAnswer: req.body.securityAnswer }
    next()
  }, router)
  app.use((err, req, res, next) => res.status(err.status || 500).json({ error: String(err) }))
  const listener = app.listen(0, '127.0.0.1')
  await once(listener, 'listening')
  t.after(() => new Promise(resolve => listener.close(resolve)))
  const url = `http://127.0.0.1:${listener.address().port}`
  const request = (route, method, body, headers = {}) => fetch(url + route, { method, headers: { 'content-type': 'application/json', ...headers }, body: JSON.stringify(body) })

  await t.test('PUT anonimo persiste alteracao; DELETE e POST anonimos sao bloqueados', async () => {
    const response = await request(`/api/Products/${product.id}`, 'PUT', { description: 'Unauthorized edit' })
    assert.equal(response.status, 200)
    await product.reload()
    assert.equal(product.description, 'Unauthorized edit')
    assert.equal((await request(`/api/Products/${product.id}`, 'DELETE', {})).status, 401)
    assert.equal((await request('/api/Products', 'POST', { name: 'Unexpected' })).status, 401)
    assert.equal(await ProductModel.count(), 1)
  })
  await t.test('controle no PUT bloqueia alteracao e preserva persistencia', async () => {
    const response = await request(`/api/Products/${product.id}`, 'PUT', { description: 'Should not persist' }, { 'x-test-protected': 'yes' })
    assert.equal(response.status, 401)
    await product.reload()
    assert.equal(product.description, 'Unauthorized edit')
  })
  await t.test('layout com traversal devolve inicio do package.json real fora de views', async () => {
    const response = await request('/dataerasure', 'POST', { layout: '../package.json' }, { 'x-test-session': 'yes' })
    assert.equal(response.status, 200)
    assert.equal(await response.text(), read('package.json').slice(0, 100) + '......')
  })
  await t.test('allowlist de campos remove layout; mesma entrada nao devolve arquivo', async () => {
    const response = await request('/dataerasure', 'POST', { layout: '../package.json' }, { 'x-test-session': 'yes', 'x-test-protected': 'yes' })
    assert.equal(response.status, 200)
    const body = await response.text()
    assert.ok(body.includes('Your erasure request will be processed shortly'))
    assert.ok(!body.includes(read('package.json').slice(0, 100)))
  })
  await t.test('sem sessao nao le arquivo; blacklist existente rejeita ftp', async () => {
    const anonymous = await request('/dataerasure', 'POST', { layout: '../package.json' })
    assert.equal(anonymous.status, 500)
    assert.match(await anonymous.text(), /Blocked illegal activity/)
    const forbidden = await request('/dataerasure', 'POST', { layout: '../ftp/example.txt' }, { 'x-test-session': 'yes' })
    assert.equal(forbidden.status, 500)
    assert.match(await forbidden.text(), /File access not allowed/)
  })
})
