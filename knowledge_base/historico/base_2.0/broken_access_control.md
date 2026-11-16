---
schema_versao: '1.0'
categoria: broken_access_control
versao_documento: '2.0'
status: PRONTO
fontes:
- titulo: Authorization Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
  consultado_em: '2026-11-03'
- titulo: Insecure Direct Object Reference Prevention Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-639: Authorization Bypass Through User-Controlled Key'
  url: https://cwe.mitre.org/data/definitions/639.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-862: Missing Authorization'
  url: https://cwe.mitre.org/data/definitions/862.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-863: Incorrect Authorization'
  url: https://cwe.mitre.org/data/definitions/863.html
  consultado_em: '2026-11-03'
- titulo: 'CWE-807: Reliance on Untrusted Inputs in a Security Decision'
  url: https://cwe.mitre.org/data/definitions/807.html
  consultado_em: '2026-11-03'
---
## 1. Descrição e sinais

Controle de acesso decide quem pode executar qual operação sobre qual recurso. Estar autenticado não prova ser o dono do recurso. Sinais: rota que busca ou altera um registro pelo ID recebido sem filtrar pelo usuário, operação privilegiada sem verificação de papel, e decisão baseada em valor que o cliente envia, como cookie, cabeçalho ou campo do corpo.

## 2. Origem e condições

Separe três situações: a verificação não existe; ela existe, mas está errada; ou ela depende de dado controlado pelo cliente. Rastreie a identidade validada pelo servidor, o papel e o recurso solicitado. IDs ou papéis recebidos na requisição não substituem essa identidade. Confira middlewares e camadas anteriores antes de afirmar a falha: uma verificação pode já existir fora do trecho analisado.

## 3. Impactos e interpretação

A falha pode expor ou alterar dados de outro usuário com o mesmo nível de acesso (horizontal) ou dar acesso a funções de nível superior (vertical). Um identificador longo ou aleatório dificulta adivinhar, mas não é autorização: se a referência vazar, o acesso continua possível.

## 4. Mitigação por mecanismo

### Escopo do usuário
Prefira buscar o recurso dentro do que pertence ao usuário autenticado, em vez de buscar na tabela inteira e conferir depois.
### Verificação por objeto
Quando o escopo não for possível, carregue o objeto e compare o dono com a identidade do servidor antes de devolver ou alterar. Aplique a mesma regra a leitura, criação, alteração, exclusão e exportação.
### Papéis e funções
Verifique a permissão no servidor em cada requisição. Negue por padrão e conceda o mínimo necessário.
### Decisões de segurança
Mantenha o estado sensível no servidor. Se um dado precisar ficar no cliente, proteja sua integridade com assinatura. Cookies, cabeçalhos e campos ocultos podem ser alterados.
### Respostas de falha
Trate a recusa de forma centralizada. Se a existência do recurso for sensível, responda igual para inexistente e sem permissão.

## 5. Preservação funcional

Mantenha o acesso legítimo: donos, administradores e recursos públicos previstos pela aplicação continuam funcionando. Não invente papéis nem bloqueie a operação inteira como correção. Preserve o formato da resposta e as mensagens existentes. Se a regra de negócio não estiver clara no código, restrinja o mínimo necessário e registre a suposição.

## 6. Exemplo genérico

Registro buscado somente pelo ID recebido:
```typescript
const nota = await notas.findById(entrada.notaId);
return nota;
```
Busca limitada à identidade autenticada pelo servidor:
```typescript
const nota = await notas.findOne({ id: entrada.notaId, donoId: sessao.usuarioId });
return nota;
```
Decisão baseada em dado do cliente e a versão com o papel da sessão:
```typescript
if (req.cookies.papel === 'admin') liberar();

if (sessao.papel === 'admin') liberar();
```

## 7. Limitações e verificação

Os exemplos supõem sessão confiável e semântica conhecida do repositório. Teste com dois usuários: autenticado como A, tente ler, alterar e excluir recursos de B. Teste também papéis diferentes, recurso inexistente e usuário sem sessão. Filtrar por dono não resolve path traversal, redirecionamento aberto, SSRF ou mass assignment, que têm documentos próprios.
