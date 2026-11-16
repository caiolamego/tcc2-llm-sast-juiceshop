declare const req: any
declare function fetch(url: string): Promise<any>

async function vulnerable() {
  const url = req.body.imageUrl
  // ruleid: tcc.http.security.request-url-fetch
  return await fetch(url)
}

async function safeConstant() {
  const url = 'https://images.example.org/a.png'
  // ok: tcc.http.security.request-url-fetch
  return await fetch(url)
}
