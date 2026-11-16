import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { spawnSync } from 'node:child_process'
import ts from 'typescript'

const root = process.cwd()
const project = path.resolve(root, '../..')
const evidenceRoot = path.join(project, 'outputs/cobertura_funcional/FINAIS_20261102/subavaliacoes')
const hash = (value: Buffer | string) => crypto.createHash('sha256').update(value).digest('hex')
const guardSpec = 'src/app/app.guard.spec.ts'
const ipSpec = 'src/app/last-login-ip/last-login-ip.component.spec.ts'

const guardNames = [
  ...['should be created', 'should open for authenticated users', 'should close for anonymous users',
    'returns payload from decoding a valid JWT', 'returns nothing when decoding an invalid JWT',
    'returns nothing when decoding an non-existing JWT'].map(name => 'LoginGuard > ' + name),
  ...['AdminGuard', 'AccountingGuard'].flatMap(suite => [
    'should be created', suite === 'AdminGuard' ? 'should open for admins' : 'should open for accountants',
    'should close for regular customers', 'should close for deluxe customers',
    suite === 'AdminGuard' ? 'should close for accountants' : 'should close for admins'
  ].map(name => suite + ' > ' + name)),
  ...['should be created', 'should open for deluxe customers', 'should close for regular customers',
    'should close for admins', 'should close for accountants'].map(name => 'DeluxeGuard > ' + name)
]
const ipNames = ['should compile', 'should log JWT parsing error to console',
  'should set Last-Login IP from JWT as trusted HTML', 'should not set Last-Login IP if none is present in JWT']
  .map(name => 'LastLoginIpComponent > ' + name)

function runAngular (spec: string, label: string, expected: string[]) {
  fs.mkdirSync(evidenceRoot, { recursive: true })
  const directory = fs.mkdtempSync(path.join(evidenceRoot, label + '-'))
  const xml = path.join(directory, 'junit.xml')
  const command = ['node_modules/@angular/cli/bin/ng.js', 'test', '--watch=false', '--progress=false',
    '--reporters=junit', '--output-file=' + xml, '--include=' + spec]
  const response = spawnSync(process.execPath, command, { cwd: path.join(root, 'frontend'), encoding: 'utf8',
    timeout: 90000, env: { ...process.env, CI: 'true', NG_CLI_ANALYTICS: 'false' } })
  fs.writeFileSync(path.join(directory, 'stdout.txt'), response.stdout ?? '')
  fs.writeFileSync(path.join(directory, 'stderr.txt'), response.stderr ?? '')
  assert.equal(response.error, undefined, 'Angular child process failed: ' + response.error)
  assert.ok(fs.existsSync(xml), 'Missing child JUnit: ' + String(response.stderr).slice(-1200))
  const parser = 'import sys,json,xml.etree.ElementTree as E; r=E.parse(sys.argv[1]); print(json.dumps([{"name":n.get("name"),"file":n.get("file") or n.get("classname"),"state":"skip" if n.find("skipped") is not None else "fail" if n.find("failure") is not None or n.find("error") is not None else "pass"} for n in r.iter("testcase")]))'
  const parsed = spawnSync('python3', ['-c', parser, xml], { encoding: 'utf8' })
  assert.equal(parsed.status, 0, parsed.stderr)
  const tests: Array<{ name: string, file: string, state: string }> = JSON.parse(parsed.stdout)
  assert.deepEqual(tests.map(t => t.name).sort(), [...expected].sort(), 'Candidate must preserve the complete test inventory')
  assert.ok(tests.every(t => t.file === spec), 'Unexpected test outside the selected candidate suite')
  assert.ok(tests.every(t => t.state !== 'skip'), 'Skipped candidate tests do not prove integrity')
  const report = { spec, label, status: response.status, candidate_sha256: hash(fs.readFileSync(path.join(root, 'frontend', spec))),
    junit_sha256: hash(fs.readFileSync(xml)), tests }
  fs.writeFileSync(path.join(directory, 'resultado.json'), JSON.stringify(report, null, 2) + '\n')
  return report
}

function mutantMethod (file: string, className: string, method: string, body: string, action: () => void) {
  const source = path.join(root, 'frontend', file)
  const original = fs.readFileSync(source)
  const text = original.toString()
  const ast = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true)
  const candidates: ts.MethodDeclaration[] = []
  ts.forEachChild(ast, node => {
    if (ts.isClassDeclaration(node) && node.name?.text === className) {
      for (const member of node.members) if (ts.isMethodDeclaration(member) && member.name.getText(ast) === method) candidates.push(member)
    }
  })
  assert.equal(candidates.length, 1, 'Expected one production method to exercise the candidate tests')
  const block = candidates[0].body
  assert.ok(block)
  const mutated = Buffer.from(text.slice(0, block.getStart(ast)) + body + text.slice(block.getEnd()))
  fs.writeFileSync(source, mutated)
  try { action() } finally {
    assert.deepEqual(fs.readFileSync(source), mutated, 'Unknown concurrent edit: refusing automatic restoration')
    fs.writeFileSync(source, original)
  }
  assert.deepEqual(fs.readFileSync(source), original)
}

function detects (report: ReturnType<typeof runAngular>, name: string) {
  assert.equal(report.status, 1, 'Candidate must reject the deliberate production regression')
  assert.ok(report.tests.some(t => t.name === name && t.state === 'fail'), 'Expected scenario did not detect its regression: ' + name)
}

void describe('TCC independent candidate frontend evaluator integrity', () => {
  void it('keeps every guard scenario and detects a broken real token decoder', () => {
    const healthy = runAngular(guardSpec, 'guard-original', guardNames)
    assert.equal(healthy.status, 0)
    assert.ok(healthy.tests.every(t => t.state === 'pass'))
    mutantMethod('src/app/app.guard.ts', 'LoginGuard', 'tokenDecode', '{ return null as any }', () => {
      detects(runAngular(guardSpec, 'guard-mutant', guardNames), 'LoginGuard > returns payload from decoding a valid JWT')
    })
  })

  void it('keeps every last IP scenario and detects missing and fabricated addresses', () => {
    const healthy = runAngular(ipSpec, 'ip-original', ipNames)
    assert.equal(healthy.status, 0)
    assert.ok(healthy.tests.every(t => t.state === 'pass'))
    mutantMethod('src/app/last-login-ip/last-login-ip.component.ts', 'LastLoginIpComponent', 'parseAuthToken', '{ void this.sanitizer; void jwtDecode; }', () => {
      detects(runAngular(ipSpec, 'ip-missing', ipNames), ipNames[2])
    })
    mutantMethod('src/app/last-login-ip/last-login-ip.component.ts', 'LastLoginIpComponent', 'parseAuthToken',
      "{ void jwtDecode; this.lastLoginIp = this.sanitizer.bypassSecurityTrustHtml('<small>unexpected</small>') }", () => {
        detects(runAngular(ipSpec, 'ip-fabricated', ipNames), ipNames[3])
      })
  })
})
