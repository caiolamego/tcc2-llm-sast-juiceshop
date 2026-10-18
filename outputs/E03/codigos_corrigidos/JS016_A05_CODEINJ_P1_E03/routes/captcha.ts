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
    function safeEval(expr: string): number {
      const operators = ['+', '-', '*'];
      let tokens = expr.match(/\d+|[+\-*]/g);
      if (!tokens) throw new Error('Invalid expression');
      let result = parseInt(tokens[0], 10);
      for (let i = 1; i < tokens.length; i += 2) {
        const operator = tokens[i];
        const operand = parseInt(tokens[i + 1], 10);
        if (!operators.includes(operator) || isNaN(operand)) {
          throw new Error('Invalid expression');
        }
        if (operator === '+') result += operand;
        else if (operator === '-') result -= operand;
        else if (operator === '*') result *= operand;
      }
      return result;
    }
    const answer = safeEval(expression).toString() // eslint-disable-line no-eval

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
