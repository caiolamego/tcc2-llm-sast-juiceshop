async function unscoped(req, res) {
  const id = req.params.id
  // ruleid: tcc.orm.security.request-id-unscoped-query
  const row = await RecordModel.findOne({ where: { id }, include: ['items'] })
  res.json(row)
}
async function scoped(req, res) {
  const id = req.params.id
  // ok: tcc.orm.security.request-id-unscoped-query
  const row = await RecordModel.findOne({ where: { id, UserId: req.user.id } })
  res.json(row)
}
async function trustedId(req, res) {
  const id = req.user.recordId
  // ok: tcc.orm.security.request-id-unscoped-query
  const row = await RecordModel.findOne({ where: { id } })
  res.json(row)
}
// Limite conhecido: verificacao posterior nao e entendida por esta regra.
// O alerta e candidato de auditoria, nao confirmacao automatica.
async function checkedAfterQuery(req, res) {
  const id = req.params.id
  // ruleid: tcc.orm.security.request-id-unscoped-query
  const row = await RecordModel.findOne({ where: { id } })
  if (row.UserId !== req.user.id) return res.sendStatus(403)
  res.json(row)
}
