---
schema_versao: '1.0'
categoria: ssrf
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: Server Side Request Forgery Prevention Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-918: Server-Side Request Forgery'
  url: https://cwe.mitre.org/data/definitions/918.html
  consultado_em: '2026-11-03'
---
## 1. Descrição e sinais

O servidor faz uma requisição para um endereço influenciado por entrada externa, sem garantir que ela vai ao destino esperado. Sinais: `fetch`, `axios`, `http.request` ou bibliotecas de download recebendo URL, host, porta ou caminho vindos do usuário ou de um documento processado.

## 2. Origem e condições

Rastreie qual parte do endereço é controlada: a URL inteira, o host ou só um parâmetro. Verifique se o cliente HTTP segue redirecionamentos e quais protocolos aceita. Valor fixo no servidor ou escolhido de uma lista não caracteriza a falha.

## 3. Impactos e interpretação

Como a requisição parte do servidor, ela pode alcançar serviços internos, metadados de nuvem (`169.254.169.254`) e endereços protegidos por firewall, além de varrer portas. Outros esquemas, como `file://`, podem expor arquivos locais. Sem resposta visível, a falha ainda pode existir. Um alerta não comprova alcance a rede interna: confira a topologia e a validação anterior.

## 4. Mitigação por mecanismo

### Destinos conhecidos
Quando a aplicação fala com sistemas identificados, use uma lista de permissão. Evite receber a URL completa: valide o host e monte esquema, porta e caminho no servidor.
### Destinos arbitrários
Quando a lista for inviável, como em webhooks, bloqueie endereços internos sabendo que esse filtro pode ser contornado. Inclua loopback (`127.0.0.0/8`, `::1`), redes privadas (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16`, `fe80::/10`), `fc00::/7` e `0.0.0.0/8`. Para domínios, verifique todos os registros A e AAAA.
### Protocolos e redirecionamentos
Restrinja a HTTP e HTTPS e desabilite o seguimento automático de redirecionamentos, que pode contornar a validação.
### DNS rebinding
A resolução usada na validação pode diferir da usada na conexão. Conecte-se ao IP validado, mantendo o hostname nos cabeçalhos e na verificação de certificado.
### Rede
Limite as saídas do servidor por firewall e segmentação, pois a aplicação não deve ser a única barreira.

## 5. Preservação funcional

Mantenha os destinos legítimos, os parâmetros enviados, o timeout e o formato da resposta. Levante quais domínios são usados hoje antes de criar a lista. Não remova a integração nem substitua a chamada por uma resposta fixa. Para destinos recusados, use o tratamento de erro existente.

## 6. Exemplo genérico

URL recebida diretamente:
```typescript
app.post('/importar', async (req, res) => {
  const resposta = await fetch(req.body.url);
  res.send(await resposta.text());
});
```
Host validado por lista, sem seguir redirecionamentos:
```typescript
const HOSTS_PERMITIDOS = new Set(['dados.exemplo.org']);

app.post('/importar', async (req, res) => {
  const url = new URL(req.body.url);
  if (url.protocol !== 'https:' || !HOSTS_PERMITIDOS.has(url.hostname)) {
    return res.status(400).send('Destino não permitido');
  }
  const resposta = await fetch(url, { redirect: 'error' });
  res.send(await resposta.text());
});
```

## 7. Limitações e verificação

O exemplo não trata DNS rebinding e supõe que `new URL` lança erro em entrada inválida, que precisa ser tratado pela rota. Teste destinos válidos, IPs internos, formas alternativas de IP, redirecionamentos, outros esquemas e hosts que resolvem para rede interna. Validar o destino não decide quem pode acionar a integração.
