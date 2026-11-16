---
schema_versao: '1.0'
categoria: authentication_failures
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: Authentication Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: Password Storage Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

Autenticação confirma identidade; atualização de credenciais e limitação de tentativas têm requisitos próprios. Troca de senha pode exigir prova recente e confiável de identidade.

## 2. Origem e condições

Identifique sessão, credencial apresentada e verificador. Verifique se há reautenticação anterior ou fluxo de recuperação independente; a mera ausência local de uma checagem não prova que falta no sistema.

## 3. Impactos e interpretação

A falha pode permitir tomada de conta ou tentativas ilimitadas. Respostas que revelam existência de usuários também afetam o risco; compare o comportamento observado.

## 4. Mitigação por mecanismo

### Alteração de senha
No fluxo autenticado, verifique a senha atual ou reautenticação equivalente definida pelo sistema. Recuperação utiliza prova distinta, com validade e uso controlados.
### Credenciais
Compare com verificador apropriado aos hashes armazenados; não registre senhas nem as devolva.
### Tentativas
Imponha controles de frequência e tratamento consistente; considere abuso de bloqueio para impedir acesso legítimo.

## 5. Preservação funcional

Preserve login, recuperação e mudança legítima. Não reutilize uma credencial do corpo como identidade de sessão. Evite alterações cosméticas ou mensagens novas sem necessidade.

## 6. Exemplo genérico

Vulnerável em fluxo que exige senha atual:
```typescript
await credentials.update(session.userId, input.newPassword);
```
Exemplo com verificação abstrata de credencial:
```typescript
if (!await credentials.verify(session.userId, input.currentPassword)) return existingFailure();
await credentials.update(session.userId, input.newPassword);
```

## 7. Limitações e verificação

As APIs são ilustrativas; verifique hashing e política do sistema real. Teste senha errada, sessão ausente, recuperação e limites. Exigir senha atual no fluxo de recuperação pode quebrar sua finalidade.
