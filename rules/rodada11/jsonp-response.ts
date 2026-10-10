function candidate(req, res) {
  // ruleid: tcc.exposure.security.jsonp-response
  res.jsonp({ email: session.email });
}
function safe(req, res) {
  // ok: tcc.exposure.security.jsonp-response
  res.json({ email: session.email });
}
function publicData(req, res) {
  // Falso positivo conhecido: dado intencionalmente publico, sem sessao.
  // ruleid: tcc.exposure.security.jsonp-response
  res.jsonp({ weather: 'sunny' });
}
