---
schema_versao: '1.0'
categoria: open_redirect
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: Unvalidated Redirects and Forwards Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-601: URL Redirection to Untrusted Site'
  url: https://cwe.mitre.org/data/definitions/601.html
  consultado_em: '2026-11-03'
- titulo: 'Express: Response (res.redirect)'
  url: https://expressjs.com/en/5x/api/response
  consultado_em: '2026-11-03'
---
## 1. Descrição e sinais

A aplicação usa uma entrada externa como destino de redirecionamento. Sinais: `res.redirect`, cabeçalho `Location` ou navegação do cliente recebendo valor de consulta, corpo, cookie ou cabeçalho, como `next`, `url` ou `returnTo`.

## 2. Origem e condições

Rastreie o valor até o redirecionamento. `res.redirect` aceita URL completa de outro site, além de caminhos relativos. Identifique todas as fontes, incluindo cookies, campos ocultos e cabeçalhos, que também podem ser alterados. Destino fixo ou escolhido pelo servidor não caracteriza a falha.

## 3. Impactos e interpretação

O link começa com o domínio legítimo, o que torna o phishing mais convincente e pode levar ao roubo de credenciais. Encaminhamentos internos também podem alcançar funções que deveriam exigir autorização. Um alerta nesse ponto não prova o desvio: confira se o destino já é restringido antes.

## 4. Mitigação por mecanismo

### Evitar a entrada
Quando possível, não receba a URL de destino do usuário.
### Mapeamento
Receba um nome curto ou identificador e converta-o no servidor para o destino completo. Essa é a opção de maior proteção; verifique se a enumeração de valores não revela destinos sensíveis.
### Destinos locais
Para retorno dentro da própria aplicação, aceite apenas caminhos locais. Lembre que `//dominio` e `/\dominio` podem ser interpretados pelo navegador como outro host.
### Lista de destinos externos
Use um parser de URL mantido e compare esquema, host canônico e porta efetiva com uma lista explícita. Rejeite userinfo e entradas ambíguas. Não compare por prefixo, sufixo ou substring. Redirecione para a URL já validada, sem transformá-la depois.

## 5. Preservação funcional

Mantenha os destinos legítimos atuais, incluindo os que a aplicação redireciona de propósito, e o código de status existente. Antes de restringir, levante quais destinos são usados hoje. Para valores recusados, siga o tratamento de erro existente da rota; não remova o redirecionamento.

## 6. Exemplo genérico

Destino recebido diretamente:
```typescript
app.get('/sair', (req, res) => {
  res.redirect(String(req.query.destino));
});
```
Destino convertido no servidor:
```typescript
const DESTINOS: Record<string, string> = {
  inicio: '/',
  ajuda: 'https://ajuda.exemplo.org/',
};

app.get('/sair', (req, res) => {
  const destino = DESTINOS[String(req.query.destino)];
  if (!destino) return res.status(400).send('Destino inválido');
  res.redirect(destino);
});
```
Comparação por partes da URL, quando a entrada precisa ser uma URL:
```typescript
const url = new URL(entrada);
const permitido = url.protocol === 'https:' && url.username === '' &&
  url.password === '' && HOSTS_PERMITIDOS.has(url.hostname);
if (!permitido) throw new Error('Destino não permitido');
res.redirect(url.href);
```

## 7. Limitações e verificação

Os exemplos supõem uma lista conhecida; em `Record`, use chaves próprias ou `Map` para evitar nomes herdados. Teste destinos válidos, outros hosts, `//host`, `/\host`, userinfo, maiúsculas, codificação e valores ausentes. Restringir o destino não substitui a autorização do recurso de destino.
