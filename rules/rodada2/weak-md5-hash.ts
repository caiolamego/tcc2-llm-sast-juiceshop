declare const crypto: any
declare const security: any
declare const model: any
declare const password: string

function legacyHash(value: string) {
  // ruleid: tcc.crypto.security.md5-hash
  return crypto.createHash('md5').update(value).digest('hex')
}

function passwordSetter() {
  model.setDataValue('password', security.hash(password))
}

function safePasswordDerivation(value: string) {
  // ok: tcc.crypto.security.md5-hash
  return crypto.scryptSync(value, 'salt', 64)
}

function sha256ForChecksum(value: string) {
  // ok: tcc.crypto.security.md5-hash
  return crypto.createHash('sha256').update(value).digest('hex')
}
