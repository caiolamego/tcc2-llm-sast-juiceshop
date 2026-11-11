import { describe, it, mock } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import ts from 'typescript'

interface Snippet { snippet: string, vulnLines: number[], neutralLines: number[] }
interface CodingModule {
  getCodeChallenges: () => Promise<Map<string, Snippet>>
  findFilesWithCodeChallenges: (paths: string[]) => Promise<Array<{ path: string, content: string }>>
}

// Transpile the entire real module. Only its filesystem/logger dependencies are
// supplied by the evaluator; extraction, traversal and cache remain target code.
function loadModule (entries: Record<string, string>, unreadable: string[] = []) {
  const files = new Map(Object.entries(entries).map(([name, content]) => [path.resolve(name), content]))
  const blocked = new Set(unreadable.map(name => path.resolve(name)))
  const warn = mock.fn()
  const lstat = mock.fn(async (name: string) => {
    const resolved = path.resolve(name)
    if (files.has(resolved)) return { isDirectory: () => false }
    if ([...files.keys()].some(file => file.startsWith(resolved + path.sep))) return { isDirectory: () => true }
    throw new Error(`ENOENT: ${name}`)
  })
  const readdir = mock.fn(async (name: string) => {
    const prefix = path.resolve(name) + path.sep
    return [...new Set([...files.keys()].filter(file => file.startsWith(prefix))
      .map(file => file.slice(prefix.length).split(path.sep)[0]))].sort()
  })
  const readFile = mock.fn(async (name: string) => {
    const resolved = path.resolve(name)
    if (blocked.has(resolved)) throw new Error(`EACCES: ${name}`)
    if (!files.has(resolved)) throw new Error(`ENOENT: ${name}`)
    return files.get(resolved)
  })
  const source = fs.readFileSync('lib/codingChallenges.ts', 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true }
  }).outputText
  const nativeRequire = createRequire(path.resolve('lib/codingChallenges.ts'))
  const module = { exports: {} }
  const requireDependency = (name: string) => {
    if (name === 'node:fs/promises') return { lstat, stat: lstat, readdir, readFile }
    if (name === './logger') return { warn }
    return nativeRequire(name)
  }
  vm.runInNewContext(output, { module, exports: module.exports, require: requireDependency }, {
    filename: 'lib/codingChallenges.ts', timeout: 1000
  })
  return { target: module.exports as CodingModule, files, warn, readFile }
}

function block (key: string, body: string[], ending = '\n', prefix = '//') {
  return [`${prefix} vuln-code-snippet start ${key}`, ...body, `${prefix} vuln-code-snippet end ${key}`].join(ending)
}

function checkSnippet (actual: Snippet | undefined, code: string, vulnerable: number[], neutral: number[]) {
  assert.ok(actual)
  assert.equal(actual.snippet, code)
  // Arrays created inside a VM have a different prototype; compare host arrays.
  assert.deepEqual([...actual.vulnLines], vulnerable)
  assert.deepEqual([...actual.neutralLines], neutral)
}

void describe('TCC coding challenge extraction contracts', () => {
  void it('assigns vulnerable and neutral lines to their own dynamic challenge keys', async () => {
    const body = [
      'const first = 1 // vuln-code-snippet vuln-line alphaCase',
      'const second = 2 // vuln-code-snippet neutral-line alphaCase',
      'const third = 3 // vuln-code-snippet vuln-line betaCase',
      'return third // vuln-code-snippet neutral-line betaCase'
    ]
    const { target } = loadModule({ 'routes/tcc-fixture.ts': block('alphaCase  betaCase ', body) })
    const challenges = await target.getCodeChallenges()
    assert.deepEqual([...challenges.keys()].sort(), ['alphaCase', 'betaCase'])
    const expected = 'const first = 1\nconst second = 2\nconst third = 3\nreturn third'
    checkSnippet(challenges.get('alphaCase'), expected, [1], [2])
    checkSnippet(challenges.get('betaCase'), expected, [3], [4])
  })

  void it('removes hidden lines and blocks before numbering the visible snippet', async () => {
    const source = block('visibleCase', [
      'const hidden = 0 // vuln-code-snippet hide-line',
      '// vuln-code-snippet hide-start',
      'const hiddenBlock = 1',
      '// vuln-code-snippet hide-end',
      'const answer = 42 // vuln-code-snippet vuln-line visibleCase',
      'return answer // vuln-code-snippet neutral-line visibleCase'
    ])
    const { target } = loadModule({ 'routes/tcc-visible.ts': source })
    checkSnippet((await target.getCodeChallenges()).get('visibleCase'), 'const answer = 42\nreturn answer', [1], [2])
  })

  for (const [name, ending] of [['LF', '\n'], ['CRLF', '\r\n'], ['CR', '\r']] as const) {
    void it(`preserves code and one-based marker positions with ${name} line endings`, async () => {
      const source = block('lineCase', [
        'const safe = 1 // vuln-code-snippet neutral-line lineCase',
        'const value = safe + 1 // vuln-code-snippet vuln-line lineCase',
        'return value'
      ], ending)
      const { target } = loadModule({ 'routes/tcc-lines.ts': source })
      checkSnippet((await target.getCodeChallenges()).get('lineCase'),
        ['const safe = 1', 'const value = safe + 1', 'return value'].join(ending), [2], [1])
    })
  }

  void it('extracts hash-comment markers from data files', async () => {
    const source = block('dataCase', [
      'name: normal # vuln-code-snippet neutral-line dataCase',
      'value: example # vuln-code-snippet vuln-line dataCase'
    ], '\n', '#')
    const { target } = loadModule({ 'data/tcc-fixture.yml': source })
    checkSnippet((await target.getCodeChallenges()).get('dataCase'), 'name: normal\nvalue: example', [2], [1])
  })

  void it('discovers nested marked files and ignores unrelated file contents', async () => {
    const first = block('firstCase', ['first() // vuln-code-snippet vuln-line firstCase'])
    const second = block('secondCase', ['second() // vuln-code-snippet neutral-line secondCase'])
    const { target } = loadModule({
      'routes/first.ts': first, 'routes/nested/second.ts': second,
      'routes/plain.ts': 'const normal = 1',
      'routes/not-a-boundary.ts': '// vuln-code-snippet vuln-line orphanCase'
    })
    const found = await target.findFilesWithCodeChallenges(['./routes'])
    assert.deepEqual([...found].map(file => path.relative(path.resolve('routes'), file.path)).sort(),
      ['first.ts', path.join('nested', 'second.ts')])
    assert.equal(found.find(file => file.path.endsWith('first.ts'))?.content, first)
    const challenges = await target.getCodeChallenges()
    assert.deepEqual([...challenges.keys()].sort(), ['firstCase', 'secondCase'])
    checkSnippet(challenges.get('firstCase'), 'first()', [1], [])
    checkSnippet(challenges.get('secondCase'), 'second()', [], [1])
  })

  void it('continues discovery and logs the path when one marked file cannot be read', async () => {
    const { target, warn } = loadModule({
      'routes/blocked.ts': block('blockedCase', ['unavailable()']),
      'routes/available.ts': block('availableCase', ['available()'])
    }, ['routes/blocked.ts'])
    const found = await target.findFilesWithCodeChallenges(['./routes'])
    assert.equal(found.length, 1)
    assert.equal(path.basename(found[0].path), 'available.ts')
    assert.equal(warn.mock.callCount(), 1)
    assert.ok(String(warn.mock.calls[0].arguments[0]).includes('blocked.ts'))
  })

  void it('rejects a snippet with a missing closing boundary', async () => {
    const { target } = loadModule({
      'routes/tcc-broken.ts': '// vuln-code-snippet start brokenCase\nconst value = 1'
    })
    await assert.rejects(target.getCodeChallenges(), (err: any) =>
      err.name === 'BrokenBoundary' && err.message.includes('brokenCase'))
  })

  void it('returns an empty map when no source contains a challenge boundary', async () => {
    const { target } = loadModule({ 'routes/plain.ts': 'const normal = 1' })
    assert.equal((await target.getCodeChallenges()).size, 0)
  })

  void it('reuses the completed extraction cache without rereading changed files', async () => {
    const { target, files, readFile } = loadModule({
      'routes/tcc-cache.ts': block('cacheCase', ['original() // vuln-code-snippet vuln-line cacheCase'])
    })
    const first = await target.getCodeChallenges()
    const reads = readFile.mock.callCount()
    files.set(path.resolve('routes/tcc-cache.ts'), block('replacementCase', ['replacement()']))
    const second = await target.getCodeChallenges()
    assert.equal(second, first)
    assert.equal(readFile.mock.callCount(), reads)
    assert.equal(second.has('replacementCase'), false)
    checkSnippet(second.get('cacheCase'), 'original()', [1], [])
  })
})
