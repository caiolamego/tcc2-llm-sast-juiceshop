/*
 * Copyright (c) 2014-2026 Bjoern Kimminich & the OWASP Juice Shop contributors.
 * SPDX-License-Identifier: MIT
 */

import { type Request, type Response, type NextFunction } from 'express'
import { CaptchaModel } from '../models/captcha'

export function captchas () {
  return async (req: Request, res: Response) => {
    const captchaId = req.app.locals.captchaId++
    const operators = ['*', '+', '-']

    const firstTerm = Math.floor((Math.random() * 10) + 1)
    const secondTerm = Math.floor((Math.random() * 10) + 1)
    const thirdTerm = Math.floor((Math.random() * 10) + 1)

    const firstOperator = operators[Math.floor((Math.random() * 3))]
    const secondOperator = operators[Math.floor((Math.random() * 3))]

    const expression = firstTerm.toString() + firstOperator + secondTerm.toString() + secondOperator + thirdTerm.toString()
    const terms = [firstTerm, secondTerm, thirdTerm]
    const expressionOperators = [firstOperator, secondOperator]
    let answerValue = terms[0]
    let pendingOperator = expressionOperators[0]
    for (let i = 1; i < terms.length; i++) {
      if (expressionOperators[i] === '*') {
        terms[i] = terms[i - 1] * terms[i]
        terms[i - 1] = 0
      }
    }
    answerValue = terms[0] * (pendingOperator === '*' ? 1 : 1)
    let total = 0
    let currentProduct = terms[0]
    for (let i = 1; i < terms.length; i++) {
      if (expressionOperators[i - 1] === '*') {
        currentProduct = terms[i]
      } else {
        total = expressionOperators[i - 1] === '+' ? total + currentProduct : total - currentProduct
        currentProduct = terms[i]
      }
    }
    total = expressionOperators[1] === '*' ? total + currentProduct : expressionOperators[1] === '+' ? total + currentProduct : total - currentProduct
    const answer = total.toString()

    const captcha = {
      captchaId,
      captcha: expression,
      answer
    }
    const captchaInstance = CaptchaModel.build(captcha)
    await captchaInstance.save()
    res.json(captcha)
  }
}

export const verifyCaptcha = () => async (req: Request, res: Response, next: NextFunction) => {
  try {
    const captcha = await CaptchaModel.findOne({ where: { captchaId: req.body.captchaId } })
    if ((captcha != null) && req.body.captcha === captcha.answer) {
      next()
    } else {
      res.status(401).send(res.__('Wrong answer to CAPTCHA. Please try again.'))
    }
  } catch (error) {
    next(error)
  }
}
