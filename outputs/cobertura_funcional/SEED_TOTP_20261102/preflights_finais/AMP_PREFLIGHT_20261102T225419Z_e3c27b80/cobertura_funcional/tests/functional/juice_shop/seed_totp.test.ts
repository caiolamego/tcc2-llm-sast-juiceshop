import { before, describe, it, type TestContext } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import crypto from 'node:crypto'
import yaml from 'js-yaml'
import config from 'config'
import request from 'supertest'
import type { Express } from 'express'
import { createTestApp } from './helpers/setup'
import { UserModel } from '../../models/user'
import * as security from '../../lib/insecurity'

interface SeedUser {
  key: string, email: string, password: string, username?: string,
  customDomain?: boolean, role?: string, totpSecret?: string, deletedFlag?: boolean
}

let app: Express
before(async () => { app = (await createTestApp()).app }, { timeout: 60000 })

function seeds (): SeedUser[] {
  const data = yaml.safeLoad(fs.readFileSync('data/static/users.yml', 'utf8'))
  assert.ok(Array.isArray(data))
  return data as SeedUser[]
}

function account () {
  const found = seeds().filter(user => user.key === 'timo')
  assert.equal(found.length, 1, 'Expected exactly one seed account with key timo')
  return found[0]
}

function email (user: SeedUser) {
  return user.customDomain ? user.email : `${user.email}@${config.get<string>('application.domain')}`
}

// Independent client oracle: no otplib call or reuse of the server verifier.
// SHA-1 test vectors: https://www.rfc-editor.org/rfc/rfc6238.html#appendix-B
function totp (secret: string, epochMs: number, digits = 6) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  const normalized = secret.toUpperCase().replace(/=+$/, '')
  assert.ok(/^[A-Z2-7]+$/.test(normalized), 'Seed must supply a usable Base32 key')
  let value = 0
  let bits = 0
  const decoded: number[] = []
  for (const character of normalized) {
    value = (value << 5) | alphabet.indexOf(character)
    bits += 5
    if (bits >= 8) {
      bits -= 8
      decoded.push((value >>> bits) & 255)
      value &= (1 << bits) - 1
    }
  }
  assert.ok(decoded.length > 0)
  const counter = Buffer.alloc(8)
  counter.writeBigUInt64BE(BigInt(Math.floor(epochMs / 30000)))
  const digest = crypto.createHmac('sha1', Buffer.from(decoded)).update(counter).digest()
  const offset = digest[digest.length - 1] & 15
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % (10 ** digits)).padStart(digits, '0')
}

const instant = Date.UTC(2030, 0, 2, 12, 0, 5)
// Baseline identities are fixed independently of the candidate YAML; credentials
// remain configurable so a valid secret/password rotation is not rejected.
const requiredSeedKeys = [
  'admin', 'jim', 'bender', 'bjoernGoogle', 'ciso', 'support', 'morty', 'rapper',
  'jannik', 'timo', 'amy', 'bjoern', 'bjoernOwasp', 'chris', 'accountant', 'uvogin',
  'test', 'john', 'emma', 'stan', 'evm', 'LetUsTest', 'basil'
]
function freeze (context: TestContext) { context.mock.timers.enable({ apis: ['Date'], now: instant }) }

function secret (user: SeedUser) {
  assert.ok(typeof user.totpSecret === 'string' && user.totpSecret.length > 0, 'Seeded second factor must remain configured')
  return user.totpSecret
}

async function firstFactor (user: SeedUser) {
  const response = await request(app).post('/rest/user/login').send({ email: email(user), password: user.password })
  assert.equal(response.status, 401)
  assert.equal(response.body.status, 'totp_token_required')
  assert.equal(typeof response.body.data.tmpToken, 'string')
  assert.equal(response.body.authentication, undefined)
  return response.body.data.tmpToken as string
}

function acceptedWindow (key: string) {
  return new Set([-30000, 0, 30000].map(delta => totp(key, instant + delta)))
}

void describe('TCC static seed TOTP contracts', () => {
  void it('matches the independent client oracle to published SHA1 TOTP vectors', () => {
    const key = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ' // RFC test key, not the seed credential.
    const vectors: Array<[number, string]> = [
      [59, '94287082'], [1111111109, '07081804'], [1111111111, '14050471'],
      [1234567890, '89005924'], [2000000000, '69279037'], [20000000000, '65353130']
    ]
    for (const [epoch, expected] of vectors) assert.equal(totp(key, epoch * 1000, 8), expected)
  })

  void it('preserves the declared identities and passwords of all static seed users', async () => {
    const declared = seeds()
    assert.deepEqual(declared.map(user => user.key).sort(), [...requiredSeedKeys].sort())
    for (const user of declared) {
      const persisted = await UserModel.findOne({ where: { email: email(user) }, paranoid: false })
      assert.ok(persisted, `Missing seed account: ${user.key}`)
      assert.equal(persisted.password, security.hash(user.password))
      if (user.role !== undefined) assert.equal(persisted.role, user.role)
      if (user.username !== undefined) assert.equal(persisted.username, user.username)
      if (user.deletedFlag) assert.ok(persisted.deletedAt)
    }
  })

  void it('persists the configured second factor for the target seed account', async () => {
    const user = account()
    const key = secret(user)
    assert.match(totp(key, instant), /^\d{6}$/)
    const persisted = await UserModel.findOne({ where: { email: email(user) } })
    assert.ok(persisted)
    assert.equal(persisted.totpSecret, key)
  })

  void it('rejects an incorrect seed password without issuing a temporary login proof', async () => {
    const user = account()
    const response = await request(app).post('/rest/user/login')
      .send({ email: email(user), password: user.password + '-incorrect-fixture' })
    assert.equal(response.status, 401)
    assert.equal(response.body.data?.tmpToken, undefined)
    assert.equal(response.body.authentication, undefined)
  })

  void it('requires the second factor after a correct seed password', async (context) => {
    freeze(context)
    const user = account()
    const temporary = await firstFactor(user)
    assert.equal(security.verify(temporary), true)
    const proof = security.decode(temporary)
    const persisted = await UserModel.findOne({ where: { email: email(user) } })
    assert.ok(persisted)
    assert.equal(proof.userId, persisted.id)
    assert.equal(proof.type, 'password_valid_needs_second_factor_token')
    const protectedResponse = await request(app).get('/rest/2fa/status').set('Authorization', `Bearer ${temporary}`)
    assert.equal(protectedResponse.status, 401)
  })

  void it('completes real seed login using an independently calculated current TOTP', async (context) => {
    freeze(context)
    const user = account()
    const temporary = await firstFactor(user)
    const response = await request(app).post('/rest/2fa/verify')
      .send({ tmpToken: temporary, totpToken: totp(secret(user), instant) })
    assert.equal(response.status, 200)
    const auth = response.body.authentication
    assert.equal(auth.umail, email(user))
    assert.equal(typeof auth.bid, 'number')
    assert.equal(security.verify(auth.token), true)
    const persisted = await UserModel.findOne({ where: { email: email(user) } })
    assert.ok(persisted)
    assert.equal(security.decode(auth.token).data.id, persisted.id)
    const status = await request(app).get('/rest/2fa/status').set('Authorization', `Bearer ${auth.token}`)
    assert.equal(status.status, 200)
    assert.equal(status.body.setup, true)
    const who = await request(app).get('/rest/user/whoami').set('Cookie', `token=${auth.token}`)
    assert.equal(who.status, 200)
    assert.equal(who.body.user.id, persisted.id)
    assert.equal(who.body.user.email, email(user))
  })

  void it('rejects an incorrect TOTP for the real seed login challenge', async (context) => {
    freeze(context)
    const user = account()
    const temporary = await firstFactor(user)
    const accepted = acceptedWindow(secret(user))
    let candidate = 0
    while (accepted.has(String(candidate).padStart(6, '0'))) candidate++
    const response = await request(app).post('/rest/2fa/verify')
      .send({ tmpToken: temporary, totpToken: String(candidate).padStart(6, '0') })
    assert.equal(response.status, 401)
    assert.equal(response.body.authentication, undefined)
  })

  void it('rejects a stale TOTP outside the configured time window', async (context) => {
    freeze(context)
    const user = account()
    const key = secret(user)
    const temporary = await firstFactor(user)
    const accepted = acceptedWindow(key)
    const stale = [120000, 150000, 180000, 210000, 240000, 270000]
      .map(delta => totp(key, instant - delta)).find(code => !accepted.has(code))
    assert.ok(stale, 'Need an unambiguous stale-code fixture')
    const response = await request(app).post('/rest/2fa/verify').send({ tmpToken: temporary, totpToken: stale })
    assert.equal(response.status, 401)
    assert.equal(response.body.authentication, undefined)
  })

  void it('rejects a valid current TOTP without a first-factor login proof', async (context) => {
    freeze(context)
    const response = await request(app).post('/rest/2fa/verify').send({ totpToken: totp(secret(account()), instant) })
    assert.equal(response.status, 401)
    assert.equal(response.body.authentication, undefined)
  })
})
