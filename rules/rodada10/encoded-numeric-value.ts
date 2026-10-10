import * as codec from 'z85';
function vulnerable(input) {
  const decoded = codec.decode(input).toString().split('-');
  // ruleid: tcc.integrity.security.encoded-numeric-value
  return parseInt(decoded[1]);
}
function safe(input) {
  const verified = verifyAndDecodeSignedPayload(input);
  // ok: tcc.integrity.security.encoded-numeric-value
  return parseInt(verified.amount);
}
function externalVerification(input, signature) {
  if (!verifySignature(input, signature)) return 0;
  const decoded = codec.decode(input).toString().split('-');
  // Falso positivo conhecido: integridade verificada fora do codec.
  // ruleid: tcc.integrity.security.encoded-numeric-value
  return parseInt(decoded[1]);
}
