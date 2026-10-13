---
schema_versao: '1.0'
categoria: broken_access_control
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: Authorization Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: 'CWE-22: Path Traversal'
  url: https://cwe.mitre.org/data/definitions/22.html
  consultado_em: '2026-10-13'
- titulo: Server Side Request Forgery Prevention Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: Unvalidated Redirects and Forwards Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

Controle de acesso decide quem pode operar qual recurso. Um usuário autenticado pode não ser proprietário. Acesso a caminhos, URLs e propriedades de objetos exige controles específicos.

## 2. Origem e condições

Rastreie identidade validada, papel e recurso solicitado. IDs ou papéis recebidos no corpo não substituem a identidade do servidor. Verifique se uma camada anterior aplica autorização antes de afirmar uma falha.

## 3. Impactos e interpretação

A falha pode expor ou alterar recursos de terceiros. Path traversal, SSRF e redirecionamento têm destinos e impactos diferentes; agrupar esses sinais não confirma uma causa comum.

## 4. Mitigação por mecanismo

### Recursos e propriedades
Consulte com identidade do servidor, autorize cada operação e permita apenas campos editáveis; não aplique objetos externos inteiros a entidades persistidas.
### Caminhos
Resolva caminhos dentro de uma raiz permitida por componentes; considere links simbólicos e arquivos existentes. Comparar apenas um prefixo textual é insuficiente.
### SSRF
Restrinja destinos, protocolos e portas; reavalie redirecionamentos e endereços efetivos para evitar alcançar redes internas.
### Redirecionamento
Prefira destinos locais conhecidos ou uma lista explícita; validar acesso ao recurso continua necessário.

## 5. Preservação funcional

Preserve as operações autorizadas e respostas públicas existentes. Acesso administrativo precisa de política explícita; não invente privilégios nem bloqueie todo acesso como correção.

## 6. Exemplo genérico

Exemplo abstrato vulnerável:
```typescript
const note = await notes.findById(input.noteId);
return note;
```
Consulta limitada à identidade autenticada pelo servidor:
```typescript
const note = await notes.findOne({ id: input.noteId, ownerId: session.userId });
return note;
```

## 7. Limitações e verificação

O exemplo supõe identidade de sessão confiável e semântica conhecida do repositório. Teste propriedade, papel, inexistência, caminhos especiais e destinos indiretos. Uma consulta filtrada não resolve SSRF nem traversal.
