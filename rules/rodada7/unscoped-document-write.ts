async function vulnerable(req, collection) {
  // ruleid: tcc.mongodb.security.unscoped-document-write
  await collection.update({ _id: req.body.id }, { $set: { text: req.body.text } }, { multi: false })
}
async function vulnerableSingle(req, collection) {
  const id = req.params.id
  // ruleid: tcc.mongodb.security.unscoped-document-write
  await collection.updateOne({ _id: id }, { $set: { text: req.body.text } })
}
async function protectedByOwner(req, collection) {
  // ok: tcc.mongodb.security.unscoped-document-write
  await collection.update({ _id: req.body.id, author: req.user.email }, { $set: { text: req.body.text } })
}
async function protectedSingle(req, collection) {
  // ok: tcc.mongodb.security.unscoped-document-write
  await collection.updateOne({ _id: req.params.id, ownerId: req.user.id }, { $set: { text: req.body.text } })
}
async function trustedId(req, collection) {
  // ok: tcc.mongodb.security.unscoped-document-write
  await collection.update({ _id: req.user.documentId }, { $set: { text: req.body.text } })
}
// Limite conhecido: a autorizacao anterior independente exige revisao manual.
async function checkedElsewhere(req, collection) {
  await requireOwner(req.user, req.body.id)
  // ruleid: tcc.mongodb.security.unscoped-document-write
  await collection.update({ _id: req.body.id }, { $set: { text: req.body.text } })
}
