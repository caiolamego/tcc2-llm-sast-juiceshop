import { before, describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import request from 'supertest'
import type { Express } from 'express'
import { createTestApp } from './helpers/setup'

let app: Express
before(async () => { app = (await createTestApp()).app }, { timeout: 60000 })

// ZIP_STORED fixture containing two ordinary files; no traversal or attack payload.
const archive = Buffer.from('UEsDBBQAAAAAAMOVYl1tDQUPKgAAACoAAAAVAAAAdGNjLWNvdmVyYWdlLXRleHQudHh0bm9ybWFsIGNvbXBsYWludApsaW5oYSBjb20gYWNlbnRvOiBhw6fDo28KUEsDBBQAAAAAAMOVYl1v59HeBwAAAAcAAAAWAAAAdGNjLWNvdmVyYWdlLWJ5dGVzLmJpbgD/gA0KQQBQSwECFAMUAAAAAADDlWJdbQ0FDyoAAAAqAAAAFQAAAAAAAAAAAAAAgAEAAAAAdGNjLWNvdmVyYWdlLXRleHQudHh0UEsBAhQDFAAAAAAAw5ViXW/n0d4HAAAABwAAABYAAAAAAAAAAAAAAIABXQAAAHRjYy1jb3ZlcmFnZS1ieXRlcy5iaW5QSwUGAAAAAAIAAgCHAAAAmAAAAAAA', 'base64')
const contents = new Map([
  ['tcc-coverage-text.txt', Buffer.from('normal complaint\nlinha com acento: ação\n')],
  ['tcc-coverage-bytes.bin', Buffer.from([0, 255, 128, 13, 10, 65, 0])]
])

void describe('TCC ZIP extraction contracts', () => {
  void it('extracts both normal ZIP entries preserving filenames and exact bytes', async () => {
    const directory = path.resolve('uploads/complaints')
    const before = new Set(await fs.readdir(directory))
    for (const name of contents.keys()) {
      assert.equal(before.has(name), false, 'Refuse to overwrite a pre-existing fixture')
    }
    try {
      const response = await request(app).post('/file-upload')
        .attach('file', archive, { filename: 'tcc-normal-complaint.zip', contentType: 'application/zip' })
      assert.equal(response.status, 204)
      const after = await fs.readdir(directory)
      assert.deepEqual(after.filter(name => !before.has(name)).sort(), [...contents.keys()].sort())
      for (const [name, expected] of contents) {
        assert.deepEqual(await fs.readFile(path.join(directory, name)), expected)
      }
    } finally {
      for (const name of contents.keys()) await fs.rm(path.join(directory, name), { force: true })
    }
  })

  void it('reports a corrupt ZIP instead of claiming successful extraction', async () => {
    const response = await request(app).post('/file-upload')
      .attach('file', Buffer.from('not a ZIP archive'), { filename: 'tcc-corrupt.zip', contentType: 'application/zip' })
    assert.equal(response.status, 500)
  })
})
