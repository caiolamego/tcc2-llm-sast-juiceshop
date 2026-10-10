/** Testes isolados do codigo real; persistencia, sessao e PDF simulados.
 * Sem alteracoes no Juice Shop, sem LLM e sem servidor externo.
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire, stripTypeScriptTypes } from 'node:module'
import { createHmac } from 'node:crypto'
import path from 'node:path'
import { test } from 'node:test'

const wt = process.env.JUICE_SHOP_WORKTREE
const deps = process.env.ROUND10_DEPS
assert.ok(wt && deps, 'Defina JUICE_SHOP_WORKTREE e ROUND10_DEPS')
const read = file => readFileSync(path.join(wt, file), 'utf8')
const meta = JSON.parse(readFileSync(new URL('../outputs/sast_antes/catalogo_meta.json', import.meta.url)))
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], { cwd: wt, encoding: 'utf8' }).trim(), meta.commit_alvo)
assert.equal(execFileSync('git', ['status', '--porcelain'], { cwd: wt, encoding: 'utf8' }).trim(), '')
const require = createRequire(path.join(deps, 'package.json'))
assert.equal(require('z85/package.json').version, '0.0.2')
const z85 = require('z85')
function segment(source, first, last) {
  const start = source.indexOf(first), end = source.indexOf(last, start + first.length)
  assert.ok(start >= 0 && end > start, `Ancora ausente: ${first}`)
  return source.slice(start, end)
}
function evaluate(source, expression, deps) {
  const js = stripTypeScriptTypes(source)
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\s*$/gm, '')
    .replace(/^export /gm, '')
  return new Function(...Object.keys(deps), `${js}\nreturn (${expression});`)(...Object.values(deps))
}
// Data fixa torna cupons e expiracao reproduziveis, sem mudar relogio do SO.
const now = new Date('2026-10-10T12:00:00Z').getTime()
class Clock extends Date {
  constructor(...args) { super(...(args.length ? args : [now])) }
  static now() { return now }
}
const utilsSource = read('lib/utils.ts')
const monthsSource = utilsSource.split('\n').find(line => line.startsWith('const months ='))
assert.ok(monthsSource, 'Declaracao dos meses ausente')
const utils = evaluate(monthsSource + '\n' + segment(utilsSource, 'export const toMMMYY', 'export const toISO8601'), '{toMMMYY}', {})
const security = evaluate(segment(read('lib/insecurity.ts'), 'export const generateCoupon', '// vuln-code-snippet start redirect'), '{generateCoupon, discountFromCoupon}', { utils, z85, Date: Clock })
const challengeUtils = { solveIf() {} }
const challenges = new Proxy({}, { get: (_, key) => key })
const orderSource = read('routes/order.ts')
const start = orderSource.indexOf('function calculateApplicableDiscount')
assert.ok(start >= 0)
const { calculateApplicableDiscount, campaigns } = evaluate(orderSource.slice(start), '{calculateApplicableDiscount, campaigns}', { security, challengeUtils, challenges, Date: Clock, Buffer })
const finalPrice = (basket, req, calculate = calculateApplicableDiscount) => evaluate(
  'let totalPrice = 100;\n' + segment(orderSource, 'const discount = calculateApplicableDiscount', 'const deliveryMethod ='),
  'totalPrice', { basket, req, calculateApplicableDiscount: calculate, doc: { text() {}, moveDown() {} } })

test('cupom Z85 escolhido pelo cliente e aceito e reduz preco de 100 para 10', async () => {
  const forged = z85.encode(utils.toMMMYY(new Clock()) + '-90')
  assert.equal(security.discountFromCoupon(forged), 90)
  const basket = { coupon: null, update: async values => Object.assign(basket, values) }
  const applyCoupon = evaluate(read('routes/coupon.ts'), 'applyCoupon', { security, BasketModel: { findByPk: async () => basket } })
  let response
  await applyCoupon()({ params: { id: 1, coupon: encodeURIComponent(forged) } }, { json: value => { response = value } }, error => { throw error })
  assert.deepEqual(response, { discount: 90 })
  assert.equal(basket.coupon, forged)
  assert.equal(finalPrice(basket, { body: {} }), 10)
})

test('controle de integridade rejeita alteracao e aceita cupom autentico', () => {
  const sign = value => createHmac('sha256', 'test-only-key-not-production').update(value).digest('hex')
  const valid = security.generateCoupon(10)
  const changed = z85.encode(utils.toMMMYY(new Clock()) + '-90')
  const verifiedDiscount = (value, signature) => sign(value) === signature ? security.discountFromCoupon(value) : 0
  assert.equal(verifiedDiscount(valid, sign(valid)), 10)
  assert.equal(verifiedDiscount(changed, sign(valid)), 0)
  assert.equal(security.discountFromCoupon(z85.encode('OCT20-90')), undefined)
  assert.equal(security.discountFromCoupon(undefined), undefined)
})

test('campanha vencida aceita data declarada pelo cliente e reduz preco', () => {
  const [code, campaign] = Object.entries(campaigns)[0]
  assert.ok(campaign.validOn < now)
  const request = { body: { couponData: Buffer.from(`${code}-${campaign.validOn}`).toString('base64') } }
  assert.equal(calculateApplicableDiscount({ coupon: null }, request), campaign.discount)
  assert.equal(finalPrice({ coupon: null }, request), 100 - campaign.discount)
  const wrong = { body: { couponData: Buffer.from(`${code}-${now}`).toString('base64') } }
  assert.equal(calculateApplicableDiscount({}, wrong), 0)
  assert.equal(calculateApplicableDiscount({}, { body: {} }), 0)
})

test('controle por dia do servidor rejeita campanha vencida e aceita dia vigente', () => {
  const campaign = Object.values(campaigns)[0]
  // Controle ilustrativo no harness; politica diaria UTC declarada, nao patch.
  const onServerDay = (entry, time) => new Date(entry.validOn).toISOString().slice(0, 10) === new Date(time).toISOString().slice(0, 10) ? entry.discount : 0
  assert.equal(onServerDay(campaign, now), 0)
  assert.equal(onServerDay(campaign, campaign.validOn), campaign.discount)
  assert.equal(finalPrice({}, { body: {} }, () => onServerDay(campaign, now)), 100)
})
