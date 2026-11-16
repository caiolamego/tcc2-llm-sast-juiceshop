function vulnerable(req, res, next) {
  // ruleid: tcc.validation.security.optional-validation-gate
  if (req.body.email !== undefined && req.body.password !== undefined && req.body.confirmation !== undefined) {
    req.body.email = req.body.email.trim();
  }
  next();
}
function safe(req, res, next) {
  // ok: tcc.validation.security.optional-validation-gate
  if (!req.body.email || !req.body.password || req.body.password !== req.body.confirmation) return res.sendStatus(400);
  next();
}
function externalGuard(req, res, next) {
  validateRequiredFieldsAndEquality(req.body);
  // Falso positivo conhecido: validacao externa completa.
  // ruleid: tcc.validation.security.optional-validation-gate
  if (req.body.email !== undefined && req.body.password !== undefined && req.body.confirmation !== undefined) {
    req.body.email = req.body.email.trim();
  }
  next();
}
