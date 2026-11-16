async function vulnerable(req, account) {
  if (req.body.method === 'balance') { await chargeBalance() }
  if (req.body.method === 'voucher') { await validateVoucher() }
  try {
    // ruleid: tcc.business.security.optional-mode-role-update
    await account.update({ role: 'premium' })
  } catch (err) { throw err }
}
async function protectedGuard(req, res, account) {
  if (req.body.method !== 'balance' && req.body.method !== 'voucher') {
    return res.sendStatus(400)
  }
  if (req.body.method === 'balance') { await chargeBalance() }
  if (req.body.method === 'voucher') { await validateVoucher() }
  // ok: tcc.business.security.optional-mode-role-update
  await account.update({ role: 'premium' })
}
async function protectedBranch(req, account) {
  if (req.body.method === 'balance') { await chargeBalance() }
  else if (req.body.method === 'voucher') { await validateVoucher() }
  else { throw new Error('Unsupported payment method') }
  // ok: tcc.business.security.optional-mode-role-update
  await account.update({ role: 'premium' })
}
async function noPrivilegeChange(req, account) {
  if (req.body.method === 'balance') { await chargeBalance() }
  if (req.body.method === 'voucher') { await validateVoucher() }
  // ok: tcc.business.security.optional-mode-role-update
  await account.update({ lastSeen: new Date() })
}
