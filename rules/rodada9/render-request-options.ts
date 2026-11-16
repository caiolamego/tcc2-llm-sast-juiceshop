function vulnerable(req, res) {
  // ruleid: tcc.template.security.render-request-options
  res.render('result', { ...req.body, title: 'Result' });
}
function safe(req, res) {
  // ok: tcc.template.security.render-request-options
  res.render('result', { email: req.body.email, layout: false });
}
function selected(req, res) {
  const locals = { email: req.body.email };
  // ok: tcc.template.security.render-request-options
  res.render('result', locals);
}
function externallyProtected(req, res) {
  // Falso positivo conhecido: middleware remove chaves reservadas.
  allowOnlyEmail(req);
  // ruleid: tcc.template.security.render-request-options
  res.render('result', { ...req.body });
}
