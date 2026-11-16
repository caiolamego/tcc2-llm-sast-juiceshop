import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import vm from 'node:vm'
import crypto from 'node:crypto'
import { createRequire } from 'node:module'
import { spawnSync, execFileSync } from 'node:child_process'

const target = process.cwd()
const nativeRequire = createRequire(path.join(target, 'Gruntfile.js'))
const algorithms: Record<string, string> = { md5: 'md5', sha256: 'sha256', sha384: 'sha384', sha512: 'sha512' }

function fixture () {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'tcc-grunt-'))
  fs.mkdirSync(path.join(temp, 'dist'))
  fs.writeFileSync(path.join(temp, 'package.json'), JSON.stringify({ name: 'tcc-fixture', version: '1.2.3', engines: { node: '>=20' } }))
  return temp
}

function checksumTask (cwd: string) {
  const tasks = new Map<string, any>()
  const log: any = { write: () => log, writeln: () => log, ok: () => log }
  log.verbose = log
  const grunt = {
    option: () => undefined,
    initConfig: () => {},
    file: { readJSON: (file: string) => JSON.parse(fs.readFileSync(path.join(cwd, file), 'utf8')),
      write: (file: string, data: string) => fs.writeFileSync(path.join(cwd, file), data) },
    registerTask: (name: string, ...args: any[]) => tasks.set(name, args.at(-1)),
    loadNpmTasks: () => {}, log
  }
  const module = { exports: {} }
  vm.runInNewContext(fs.readFileSync(path.join(target, 'Gruntfile.js'), 'utf8'), {
    module, exports: module.exports, require: nativeRequire, process, Buffer
  }, { filename: 'Gruntfile.js', timeout: 1000 })
  ;(module.exports as (grunt: any) => void)(grunt)
  assert.equal(typeof tasks.get('checksum'), 'function')
  return tasks.get('checksum') as () => void
}

function verifySidecar (directory: string, file: string) {
  const companions = fs.readdirSync(directory).filter(name => name.startsWith(file + '.') && algorithms[name.slice(file.length + 1)])
  assert.equal(companions.length, 1, 'Need exactly one correctly labelled checksum artifact')
  const extension = companions[0].slice(file.length + 1)
  const expected = crypto.createHash(algorithms[extension]).update(fs.readFileSync(path.join(directory, file))).digest('hex')
  assert.equal(fs.readFileSync(path.join(directory, companions[0]), 'utf8').trim(), expected)
}

void describe('TCC Grunt distribution artifact contracts', () => {
  void it('writes a correctly labelled checksum for every exact artifact byte sequence', () => {
    const cwd = fixture()
    const previous = process.cwd()
    try {
      fs.writeFileSync(path.join(cwd, 'dist/first.zip'), Buffer.from([0, 255, 128, 13, 10, 65]))
      fs.writeFileSync(path.join(cwd, 'dist/second.tgz'), Buffer.from('ordinary distribution bytes\n'))
      const run = checksumTask(cwd)
      process.chdir(cwd)
      run()
      verifySidecar(path.join(cwd, 'dist'), 'first.zip')
      verifySidecar(path.join(cwd, 'dist'), 'second.tgz')
    } finally { process.chdir(previous); fs.rmSync(cwd, { recursive: true, force: true }) }
  })

  void it('handles an empty distribution directory without inventing checksum files', () => {
    const cwd = fixture()
    const previous = process.cwd()
    try {
      const run = checksumTask(cwd)
      process.chdir(cwd)
      run()
      assert.deepEqual(fs.readdirSync(path.join(cwd, 'dist')), [])
    } finally { process.chdir(previous); fs.rmSync(cwd, { recursive: true, force: true }) }
  })

  void it('packages the fixture with the real Grunt tasks and preserves its manifest and files', () => {
    const cwd = fixture()
    try {
      fs.mkdirSync(path.join(cwd, 'build/reports'), { recursive: true })
      fs.mkdirSync(path.join(cwd, 'views'))
      fs.writeFileSync(path.join(cwd, 'LICENSE'), 'TCC fixture license\n')
      fs.writeFileSync(path.join(cwd, 'server.ts'), 'export const fixture = true\n')
      fs.writeFileSync(path.join(cwd, 'build/server.js'), 'module.exports = { fixture: true }\n')
      fs.writeFileSync(path.join(cwd, 'build/reports/omit.txt'), 'not a distribution artifact')
      fs.writeFileSync(path.join(cwd, 'views/fixture.pug'), 'p Normal fixture')
      const wrapper = path.join(cwd, 'Gruntfile.cjs')
      fs.writeFileSync(wrapper, `module.exports = function(grunt) {
        grunt.loadNpmTasks = name => grunt.loadTasks(require('node:path').join(${JSON.stringify(target)}, 'node_modules', name, 'tasks'));
        require(${JSON.stringify(path.join(target, 'Gruntfile.js'))})(grunt);
      };`)
      const script = `const grunt = require(${JSON.stringify(path.join(target, 'node_modules/grunt'))});
        grunt.tasks(['package'], { gruntfile: ${JSON.stringify(wrapper)}, base: ${JSON.stringify(cwd)}, os: 'linux', platform: 'x64', node: '24' });`
      const result = spawnSync(process.execPath, ['-e', script], { cwd, encoding: 'utf8', timeout: 60000 })
      assert.equal(result.status, 0, String(result.stderr) + String(result.stdout))
      const name = 'tcc-fixture-1.2.3_node24_linux_x64.tgz'
      const archive = path.join(cwd, 'dist', name)
      assert.ok(fs.existsSync(archive))
      const files = execFileSync('tar', ['-tzf', archive], { encoding: 'utf8' }).split('\n').filter(Boolean)
      const prefix = 'juice-shop_1.2.3/'
      for (const file of ['package.json', 'LICENSE', 'server.ts', 'build/server.js', 'views/fixture.pug']) {
        assert.ok(files.includes(prefix + file), 'Missing packaged file: ' + file)
      }
      assert.equal(files.some(file => file.includes('build/reports/omit.txt')), false)
      const manifest = JSON.parse(execFileSync('tar', ['-xOzf', archive, prefix + 'package.json'], { encoding: 'utf8' }))
      assert.equal(manifest.name, 'tcc-fixture')
      assert.equal(manifest.version, '1.2.3')
      assert.equal(manifest.engines.node, '24')
      assert.deepEqual(manifest.os, ['linux'])
      assert.deepEqual(manifest.cpu, ['x64'])
      assert.equal(execFileSync('tar', ['-xOzf', archive, prefix + 'build/server.js'], { encoding: 'utf8' }), 'module.exports = { fixture: true }\n')
      verifySidecar(path.join(cwd, 'dist'), name)
    } finally { fs.rmSync(cwd, { recursive: true, force: true }) }
  })
})
