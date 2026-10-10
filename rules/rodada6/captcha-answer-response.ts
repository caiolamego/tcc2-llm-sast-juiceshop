function exposed(res, expression, solution) {
  const payload = { captcha: expression, answer: solution, id: 42 }
  // ruleid: tcc.captcha.security.answer-in-response
  res.json(payload)
}
function direct(res, expression, solution) {
  // ruleid: tcc.captcha.security.answer-in-response
  res.json({ captcha: expression, answer: solution })
}
function protectedResponse(res, expression, solution, store) {
  const record = { captcha: expression, answer: solution, id: 42 }
  store.save(record)
  // ok: tcc.captcha.security.answer-in-response
  res.json({ id: record.id, captcha: record.captcha })
}
