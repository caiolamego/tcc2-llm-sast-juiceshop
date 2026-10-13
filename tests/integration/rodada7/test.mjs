/** Testes isolados do codigo real das rotas, com banco/autenticacao simulados.
 * Nao sobe servidor, nao executa codefixes, nao usa rede e nao chama LLM.
 * Node 24; JUICE_SHOP_WORKTREE deve apontar para o checkout limpo do commit fixado.
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import path from 'node:path'
import { test } from 'node:test'

const worktree = process.env.JUICE_SHOP_WORKTREE
assert.ok(worktree, 'Defina JUICE_SHOP_WORKTREE para o commit fixado')
const meta = JSON.parse(readFileSync(new URL('../../../outputs/sast_antes/catalogo_meta.json', import.meta.url), 'utf8'))
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: worktree, encoding: 'utf8' }).trim(), meta.commit_alvo)
assert.equal(execFileSync('git', ['status', '--porcelain'], { cwd: worktree, encoding: 'utf8' }).trim(), '', 'O alvo deve estar limpo')

function loadFactory(file, exportedName, dependencies) {
  // Apenas os dois arquivos fixados abaixo; imports sao substituidos pelos mocks.
  assert.ok(['routes/updateProductReviews.ts', 'routes/deluxe.ts'].includes(file))
  const source = readFileSync(path.join(worktree, file), 'utf8')
    .replace(/^import .*$/gm, '')
    .replace(/^export /gm, '')
  const code = stripTypeScriptTypes(source)
  return new Function(...Object.keys(dependencies), `${code}\nreturn ${exportedName};`)(...Object.values(dependencies))
}

function response() {
  return {
    statusCode: 200,
    status(code) { this.statusCode = code; return this },
    json(body) { this.body = body; return this }
  }
}

const challenges = new Proxy({}, { get: (_, name) => name })
const challengeUtils = { solveIf() {} } // Hooks desativados: nao decidem o resultado dos testes.

test('avaliacao de outro autor e modificada usando um ID escalar, sem injecao NoSQL', async () => {
  const row = { _id: 'document-1', author: 'owner@example.test', message: 'original' }
  let observedFilter
  const db = { reviewsCollection: {
    update: async (filter, change) => {
      observedFilter = filter
      const original = { ...row }
      // Simula somente igualdade por campos; o teste nao precisa de operadores NoSQL.
      const matches = Object.entries(filter).every(([key, value]) => row[key] === value)
      if (matches) Object.assign(row, change.$set)
      return { modified: matches ? 1 : 0, original: [original], updated: [{ ...row }] }
    }
  } }
  const security = { authenticatedUsers: { from: () => ({ data: { email: 'other@example.test' } }) } }
  const factory = loadFactory('routes/updateProductReviews.ts', 'updateProductReviews',
    { db, security, challenges, challengeUtils })
  const res = response()
  factory()({ body: { id: row._id, message: 'changed' } }, res, err => { throw err })
  await new Promise(resolve => setImmediate(resolve)) // A rota usa .then sem retornar a Promise.
  assert.deepEqual(observedFilter, { _id: 'document-1' })
  assert.equal(row.message, 'changed')
  assert.equal(row.author, 'owner@example.test')
  assert.equal(res.body.modified, 1)
})

async function exerciseUpgrade(body, { balance = 100, card = null } = {}) {
  const calls = { debit: 0, walletRead: 0, cardRead: 0, upgrade: 0 }
  const user = {
    id: 1, email: 'customer@example.test', role: 'customer',
    async update(change) { calls.upgrade++; Object.assign(this, change); return this }
  }
  const dependencies = {
    UserModel: { findOne: async () => user },
    WalletModel: {
      findOne: async () => { calls.walletRead++; return { balance } },
      decrement: async () => { calls.debit++ }
    },
    CardModel: { findOne: async () => { calls.cardRead++; return card } },
    security: {
      roles: { customer: 'customer', deluxe: 'deluxe' },
      deluxeToken: () => 'mock-deluxe-token', authorize: () => 'mock-session',
      authenticatedUsers: { put() {} }
    },
    utils: { queryResultToJson: value => value, getErrorMessage: err => String(err) },
    challenges, challengeUtils
  }
  const factory = loadFactory('routes/deluxe.ts', 'upgradeToDeluxe', dependencies)
  const res = response()
  await factory()({ body: { UserId: 1, ...body } }, res, err => { throw err })
  return { user, calls, res }
}

for (const [name, body] of [['ausente', {}], ['null', { paymentMode: null }], ['desconhecido', { paymentMode: 'unsupported' }]]) {
  test(`Deluxe: modo ${name} promove conta sem consultar pagamento`, async () => {
    const { user, calls, res } = await exerciseUpgrade(body)
    assert.equal(res.statusCode, 200)
    assert.equal(user.role, 'deluxe')
    assert.deepEqual(calls, { debit: 0, walletRead: 0, cardRead: 0, upgrade: 1 })
  })
}

test('controle: wallet valido consulta saldo e debita antes de promover', async () => {
  const { calls, res } = await exerciseUpgrade({ paymentMode: 'wallet' })
  assert.equal(res.statusCode, 200)
  assert.deepEqual(calls, { debit: 1, walletRead: 1, cardRead: 0, upgrade: 1 })
})

test('controle: saldo insuficiente nao promove', async () => {
  const { user, calls, res } = await exerciseUpgrade({ paymentMode: 'wallet' }, { balance: 0 })
  assert.equal(res.statusCode, 400)
  assert.equal(user.role, 'customer')
  assert.equal(calls.upgrade, 0)
  assert.equal(calls.debit, 0)
})

test('controle: cartao inexistente nao promove', async () => {
  const { user, calls, res } = await exerciseUpgrade({ paymentMode: 'card', paymentId: 'missing' })
  assert.equal(res.statusCode, 400)
  assert.equal(user.role, 'customer')
  assert.equal(calls.upgrade, 0)
  assert.equal(calls.cardRead, 1)
})
