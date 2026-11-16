function vulnerable(app, security) {
  // ruleid: tcc.authorization.security.asymmetric-method-guard
  app.delete('/api/Items/:id', security.denyAll());
  registerCrud(app);
}
function protectedPut(app, security) {
  app.put('/api/Items/:id', security.denyAll());
  // ok: tcc.authorization.security.asymmetric-method-guard
  app.delete('/api/Items/:id', security.denyAll());
  registerCrud(app);
}
function protectedAll(app, security) {
  app.use('/api/Items/:id', security.isAuthorized());
  // ok: tcc.authorization.security.asymmetric-method-guard
  app.delete('/api/Items/:id', security.denyAll());
  registerCrud(app);
}
function externalControl(app, security) {
  installAuthorization(app);
  // Falso positivo conhecido: controle nao visivel nesta regra local.
  // ruleid: tcc.authorization.security.asymmetric-method-guard
  app.delete('/api/Items/:id', security.denyAll());
  registerCrud(app);
}
