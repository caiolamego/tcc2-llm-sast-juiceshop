function collision(user, records) {
  const key = user.email.replace(/[aeiou]/gi, '*')
  // ruleid: tcc.identity.security.masked-email-selector
  return records.find({ email: key })
}
function identity(user, records) {
  // ok: tcc.identity.security.masked-email-selector
  return records.find({ email: user.email })
}
function scoped(user, records) {
  const key = user.email.replace(/[aeiou]/gi, '*')
  // ok: tcc.identity.security.masked-email-selector
  return records.find({ email: key, userId: user.id })
}
