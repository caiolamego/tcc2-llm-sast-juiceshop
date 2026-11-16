function vulnerable(current, account, nextPassword) {
  // ruleid: tcc.auth.security.optional-current-password
  if (current && security.hash(current) !== account.password) {
    throw new Error('Incorrect password')
  }
  return account.update({ password: nextPassword })
}
function protectedChange(current, account, nextPassword) {
  // ok: tcc.auth.security.optional-current-password
  if (!current || security.hash(current) !== account.password) {
    throw new Error('Incorrect password')
  }
  return account.update({ password: nextPassword })
}
function mandatoryComparison(current, account, nextPassword) {
  // ok: tcc.auth.security.optional-current-password
  if (security.hash(current) !== account.password) {
    throw new Error('Incorrect password')
  }
  return account.update({ password: nextPassword })
}
