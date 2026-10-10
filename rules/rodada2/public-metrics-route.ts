declare const app: any
declare const router: any
declare const metrics: any
declare const auth: any
declare const handler: any

// ruleid: tcc.express.security.public-metrics-route
app.get('/metrics', metrics.serveMetrics())

// ruleid: tcc.express.security.public-metrics-route
router.get('/metrics', handler)

// ok: tcc.express.security.public-metrics-route
app.get('/metrics', auth.isAuthorized(), metrics.serveMetrics())

// ok: tcc.express.security.public-metrics-route
app.get('/health', handler)
