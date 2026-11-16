function insecure (url: string, allowlist: Set<string>) {
  let allowed = false
  // ruleid: tcc.redirect.security.substring-allowlist
  for (const entry of allowlist) {
    allowed = allowed || url.includes(entry)
  }
  return allowed
}

function exact (url: string, allowlist: Set<string>) {
  // ok: tcc.redirect.security.substring-allowlist
  for (const entry of allowlist) {
    if (url === entry) return true
  }
  return false
}

function pathnameSearch (path: string, patterns: string[]) {
  // ok: tcc.redirect.security.substring-allowlist
  for (const item of patterns) {
    if (path.includes(item)) return true
  }
  return false
}
