declare const db: any
declare const req: any

function vulnerable (request: any) {
  // ruleid: tcc.mongodb.security.untrusted-id-multi-update
  return db.reviews.update({ _id: request.body.id }, { $set: { text: request.body.text } }, { multi: true })
}

function singleUpdate (request: any) {
  // ok: tcc.mongodb.security.untrusted-id-multi-update
  return db.reviews.update({ _id: request.body.id }, { $set: { text: request.body.text } }, { multi: false })
}

function validatedId (request: any) {
  const id = validateAndNormalizeId(request.body.id)
  // ok: tcc.mongodb.security.untrusted-id-multi-update
  return db.reviews.update({ _id: id }, { $set: { text: request.body.text } }, { multi: true })
}

declare function validateAndNormalizeId (value: unknown): string
