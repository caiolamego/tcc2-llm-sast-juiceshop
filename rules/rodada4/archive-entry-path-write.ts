declare const entry: any
declare const fs: any
declare const path: any

function vulnerable() {
  const fileName = entry.path
  // ruleid: tcc.archive.security.entry-path-write
  return fs.createWriteStream('uploads/' + fileName)
}

function safeBasename() {
  const fileName = path.basename(entry.path)
  // ok: tcc.archive.security.entry-path-write
  return fs.createWriteStream('uploads/' + fileName)
}

function safeStaticPath() {
  // ok: tcc.archive.security.entry-path-write
  return fs.createWriteStream('uploads/fixed.txt')
}
