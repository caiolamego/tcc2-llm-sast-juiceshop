// DOM real do painel; transporte simulado e nenhuma chamada de inferência.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { resolve } = require('node:path')
const { createRequire } = require('node:module')
const repo = resolve(__dirname, '../..')
const frontendRequire = createRequire(resolve(repo, 'workspace/wt-1/frontend/package.json'))
const { JSDOM } = frontendRequire('jsdom')

test('seleção de modelo persiste no polling, fica bloqueada na execução e chega ao POST', async () => {
  const dom = new JSDOM(readFileSync(resolve(repo, 'src/pipeline/painel/web/index.html'), 'utf8'), {
    url: 'http://127.0.0.1:8765/', runScripts: 'outside-only'
  })
  try {
    const { window } = dom
    const requests = []
    const payload = {
      modelos: ['gpt-4.1-mini', 'gpt-5.6-luna', 'gpt-6-luna'],
      ativo: false, atual: null, tentativas: [], avisos: [], log: '',
      config: { modo: 'preflight', modelo: 'gpt-6-luna', casos: ['AMP1'], estrategias: ['P1'], k: 4 },
      inferencia: { provedor: 'openai', modelo: 'gpt-6-luna', conexao: 'não consultada' }
    }
    window.setInterval = () => 0
    window.fetch = async (path, options) => {
      if (options?.method === 'POST') requests.push({ path, body: JSON.parse(options.body) })
      const data = path === '/api/token' ? { token: 'synthetic-token' } :
        path === '/api/historico' ? { execucoes: [] } :
          path === '/api/iniciar' ? { execucao: 'SYNTHETIC' } : payload
      return { ok: true, json: async () => data }
    }
    window.eval(readFileSync(resolve(repo, 'src/pipeline/painel/web/app.js'), 'utf8'))
    await new Promise(resolve => setImmediate(resolve))
    const select = window.document.getElementById('model')
    assert.equal(select.options.length, 4)
    assert.equal(select.value, 'gpt-6-luna')
    select.value = 'gpt-5.6-luna'
    window.render(payload)
    assert.equal(select.value, 'gpt-5.6-luna')
    window.render({ ...payload, ativo: true, atual: { status: 'executando', etapa: 'pipeline', decorrido_s: 1 } })
    assert.equal(select.disabled, true)
    window.render(payload)
    assert.equal(select.disabled, false)
    await window.document.getElementById('start').onclick()
    assert.equal(requests.length, 1)
    assert.equal(requests[0].path, '/api/iniciar')
    assert.deepEqual(requests[0].body, { modo: 'preflight', modelo: 'gpt-5.6-luna' })
  } finally {
    dom.window.close()
  }
})
