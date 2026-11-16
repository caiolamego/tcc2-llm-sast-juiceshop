import * as api from 'finale-rest'
// ruleid: tcc.finale.security.generated-default-writes
api.resource({ model: Account, endpoints: ['/accounts', '/accounts/:id'] })
// ok: tcc.finale.security.generated-default-writes
api.resource({ model: Account, endpoints: ['/accounts', '/accounts/:id'], actions: ['read', 'list'] })
// Limitacao: middleware seguro tambem gera alerta; confirmar fluxo manualmente.
app.post('/entries', forceAuthenticatedAuthor)
// ruleid: tcc.finale.security.generated-default-writes
api.resource({ model: Entry, endpoints: ['/entries', '/entries/:id'] })
