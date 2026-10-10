declare const collection: any
declare const req: any

function concatenated() {
  const id = req.params.id
  // ruleid: tcc.mongodb.security.dynamic-where
  return collection.find({ $where: 'this.product == ' + id })
}

function interpolated() {
  const id = req.params.id
  // ruleid: tcc.mongodb.security.dynamic-where
  return collection.find({ $where: `this.orderId === '${id}'` })
}

function safeTypedFilter() {
  const id = Number(req.params.id)
  // ok: tcc.mongodb.security.dynamic-where
  return collection.find({ product: id })
}

function safeFixedWhere() {
  // ok: tcc.mongodb.security.dynamic-where
  return collection.find({ $where: 'this.enabled === true' })
}
