function vulnerable(stock, count, next, res) {
  // ruleid: tcc.validation.security.quantity-upper-bound-only
  if (stock.quantity >= count) { next() } else { res.sendStatus(400) }
}
function protectedGuard(stock, count, next, res) {
  if (count <= 0) { return res.sendStatus(400) }
  // ok: tcc.validation.security.quantity-upper-bound-only
  if (stock.quantity >= count) { next() } else { res.sendStatus(400) }
}
function protectedCombined(stock, count, next, res) {
  // ok: tcc.validation.security.quantity-upper-bound-only
  if (Number.isInteger(count) && count > 0 && stock.quantity >= count) { next() } else { res.sendStatus(400) }
}
// Controle externo nao e interpretado pela regra: candidato precisa de revisao.
function protectedElsewhere(stock, count, next, res) {
  requirePositiveInteger(count)
  // ruleid: tcc.validation.security.quantity-upper-bound-only
  if (stock.quantity >= count) { next() } else { res.sendStatus(400) }
}
