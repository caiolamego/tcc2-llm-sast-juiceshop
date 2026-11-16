import { before, describe, it, mock } from 'node:test'
import assert from 'node:assert/strict'
import request from 'supertest'
import type { Express, Request, Response } from 'express'
import { createTestApp } from './helpers/setup'
import { captchas } from '../../routes/captcha'
import { CaptchaModel } from '../../models/captcha'

let app: Express
before(async () => { app = (await createTestApp()).app }, { timeout: 60000 })

// Expected values are calculated independently of the application's eval/parser.
const examples: Array<[number, number, string, number]> = [
  [0, 0, '2*3*4', 24], [0, 1, '2*3+4', 10], [0, 2, '2*3-4', 2],
  [1, 0, '2+3*4', 14], [1, 1, '2+3+4', 9], [1, 2, '2+3-4', 1],
  [2, 0, '2-3*4', -10], [2, 1, '2-3+4', 3], [2, 2, '2-3-4', -5]
]

void describe('TCC CAPTCHA arithmetic contracts', () => {
  for (const [first, second, expression, expected] of examples) {
    void it(`calculates and persists ${expression} = ${expected}`, async () => {
      const originalRandom = Math.random.bind(Math)
      const samples = [0.15, 0.25, 0.35, (first + 0.1) / 3, (second + 0.1) / 3]
      const random = mock.method(Math, 'random', () => samples.shift() ?? originalRandom())
      let generated: { captchaId: number, captcha: string, answer: string } | undefined
      try {
        await captchas()({ app } as Request, { json: (value: typeof generated) => { generated = value } } as Response)
      } finally {
        random.mock.restore()
      }
      assert.ok(generated)
      assert.equal(generated.captcha, expression)
      assert.equal(generated.answer, String(expected))
      const persisted = await CaptchaModel.findOne({ where: { captchaId: generated.captchaId } })
      assert.ok(persisted, 'CAPTCHA must be saved before it is returned')
      assert.equal(persisted.answer, String(expected))

      const feedback = { comment: 'TCC normal feedback', rating: 3, captchaId: generated.captchaId }
      const rejected = await request(app).post('/api/Feedbacks').send({ ...feedback, captcha: String(expected + 1) })
      assert.equal(rejected.status, 401)
      const accepted = await request(app).post('/api/Feedbacks').send({ ...feedback, captcha: String(expected) })
      assert.equal(accepted.status, 201)
      assert.equal(accepted.body.data.comment, feedback.comment)
      assert.equal(accepted.body.data.rating, 3)
    })
  }

  void it('rejects a correct-looking answer for an unknown CAPTCHA', async () => {
    const response = await request(app).post('/api/Feedbacks')
      .send({ comment: 'TCC unknown CAPTCHA', rating: 3, captchaId: -1, captcha: '9' })
    assert.equal(response.status, 401)
  })
})
