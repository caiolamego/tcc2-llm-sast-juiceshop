function vulnerable(req, campaign) {
  const fields = Buffer.from(req.body.payload, 'base64').toString().split('-');
  const date = Number(fields[1]);
  // ruleid: tcc.validation.security.client-campaign-date
  if (date == campaign.validOn) return campaign.discount;
  return 0;
}
function safe(req, campaign) {
  const date = Date.now();
  // ok: tcc.validation.security.client-campaign-date
  if (date === campaign.validOn) return campaign.discount;
  return 0;
}
function externalValidation(req, campaign) {
  if (!isActiveOnServer(campaign)) return 0;
  const date = Number(req.body.date);
  // Falso positivo conhecido: guarda temporal externa.
  // ruleid: tcc.validation.security.client-campaign-date
  if (date === campaign.validOn) return campaign.discount;
  return 0;
}
