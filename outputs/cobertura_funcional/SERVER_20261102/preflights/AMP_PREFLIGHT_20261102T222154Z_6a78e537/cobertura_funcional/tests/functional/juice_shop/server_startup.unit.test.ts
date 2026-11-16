import { describe, it, mock } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

// Exercise the actual internal function without importing server.ts and starting
// unrelated services. AST selection avoids copying its implementation into a test.
function loadStartupWrapper () {
  const source = fs.readFileSync('server.ts', 'utf8')
  const parsed = ts.createSourceFile('server.ts', source, ts.ScriptTarget.Latest, true)
  const declarations: ts.VariableDeclaration[] = []
  const visit = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === 'collectDurationPromise') {
      declarations.push(node)
    }
    ts.forEachChild(node, visit)
  }
  visit(parsed)
  assert.equal(declarations.length, 1, 'Expected exactly one startup timing wrapper')
  const initializer = declarations[0].initializer
  assert.ok(initializer)
  const end = mock.fn()
  const startTimer = mock.fn(() => end)
  const error = mock.fn()
  const compiled = ts.transpileModule(`const wrapper = ${initializer.getText(parsed)}; wrapper;`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS }
  }).outputText
  const wrapper = vm.runInNewContext(compiled, { startupGauge: { startTimer }, console: { error } }, {
    filename: 'server-startup-wrapper.js', timeout: 1000
  }) as (name: string, task: (...args: any[]) => Promise<any>) => (...args: any[]) => Promise<any>
  return { wrapper, startTimer, end, error }
}

void describe('TCC server startup contracts', () => {
  void it('forwards task arguments and result and finishes the success timer exactly once', async () => {
    const { wrapper, startTimer, end, error } = loadStartupWrapper()
    const expected = { ready: true }
    const task = mock.fn(async (...args: unknown[]) => {
      assert.deepEqual(args, ['first', 42])
      assert.equal(end.mock.callCount(), 0, 'Timer must not end before the task finishes')
      return expected
    })
    assert.equal(await wrapper('configure-test', task)('first', 42), expected)
    assert.equal(task.mock.callCount(), 1)
    assert.equal(startTimer.mock.callCount(), 1)
    assert.equal(startTimer.mock.calls[0].arguments[0].task, 'configure-test')
    assert.equal(end.mock.callCount(), 1)
    assert.equal(error.mock.callCount(), 0)
  })

  void it('logs the failing task name and rethrows the identical asynchronous error', async () => {
    const { wrapper, error } = loadStartupWrapper()
    const cause = new Error('TCC asynchronous startup failure')
    await assert.rejects(wrapper('schedule-test', async () => { throw cause })(), err => err === cause)
    assert.equal(error.mock.callCount(), 1)
    const args = error.mock.calls[0].arguments
    assert.match(args[0], /schedule-test/)
    assert.equal(args[1], cause)
  })

  void it('logs and propagates a synchronous exception from a startup task', async () => {
    const { wrapper, error } = loadStartupWrapper()
    const cause = new Error('TCC synchronous startup failure')
    await assert.rejects(wrapper('sync-test', () => { throw cause })(), err => err === cause)
    assert.equal(error.mock.callCount(), 1)
    assert.match(error.mock.calls[0].arguments[0], /sync-test/)
    assert.equal(error.mock.calls[0].arguments[1], cause)
  })
})
