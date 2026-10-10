declare const app: any
declare const rateLimit: any

function vulnerable() {
  // ruleid: tcc.express.security.trust-all-proxies-rate-limit
  app.enable('trust proxy')
  app.use('/reset', rateLimit({
    windowMs: 1000,
    keyGenerator({ headers, ip }: any) { return headers['x-forwarded-for'] ?? ip }
  }))
}

function safeTrustedProxy() {
  // ok: tcc.express.security.trust-all-proxies-rate-limit
  app.set('trust proxy', 'loopback')
  app.use('/reset', rateLimit({
    keyGenerator({ ip }: any) { return ip }
  }))
}

function noRateLimit() {
  // ok: tcc.express.security.trust-all-proxies-rate-limit
  app.enable('trust proxy')
  app.get('/health', () => 'ok')
}

function fixedKey() {
  // ok: tcc.express.security.trust-all-proxies-rate-limit
  app.enable('trust proxy')
  app.use('/reset', rateLimit({
    keyGenerator({ ip }: any) { return 'server-side-user-id' }
  }))
}
