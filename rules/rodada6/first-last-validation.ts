function vulnerable(ids, owner, model) {
  if (ids[0] && Number(owner) !== Number(ids[0])) {
    throw new Error('Not authorized')
  } else {
    // ruleid: tcc.validation.security.first-last-mismatch
    return model.create({ owner: ids[ids.length - 1] })
  }
}
function sameValue(ids, owner, model) {
  if (ids[0] && Number(owner) !== Number(ids[0])) {
    throw new Error('Not authorized')
  } else {
    // ok: tcc.validation.security.first-last-mismatch
    return model.create({ owner: ids[0] })
  }
}
function validateLast(ids, owner, model) {
  if (!ids.length || Number(owner) !== Number(ids[ids.length - 1])) {
    throw new Error('Not authorized')
  } else {
    // ok: tcc.validation.security.first-last-mismatch
    return model.create({ owner: ids[ids.length - 1] })
  }
}
