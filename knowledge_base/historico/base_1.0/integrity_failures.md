---
schema_versao: '1.0'
categoria: integrity_failures
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: 'CWE-345: Insufficient Verification of Data Authenticity'
  url: https://cwe.mitre.org/data/definitions/345.html
  consultado_em: '2026-10-13'
- titulo: Secure Code Review Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

Integridade e autenticidade dizem respeito à origem e alteração de dados ou componentes. Um dado marcado como confiável pelo cliente não se torna confiável no servidor.

## 2. Origem e condições

Identifique produtor, transporte, armazenamento e quem pode editar o conteúdo. Nem todo objeto externo precisa de assinatura: a garantia depende da decisão tomada a partir dele.

## 3. Impactos e interpretação

Conteúdo adulterado pode influenciar privilégios ou comportamento. Uma classificação de autenticidade não prova que há controle adversarial; investigue a fronteira de confiança.

## 4. Mitigação por mecanismo

### Decisões internas
Derive permissões e propriedades confiáveis de estado controlado pelo servidor.
### Conteúdo assinado
Verifique assinatura, chave autorizada, finalidade e validade antes de utilizar dados; um checksum sem chave não autentica o produtor.
### Componentes
Controle origem e versões de dependências e dados de configuração; não execute conteúdo externo apenas porque veio de um local esperado.

## 5. Preservação funcional

Preserve integrações legítimas e formato dos dados. Não substitua verificações por uma comparação parcial nem aceite indiscriminadamente mensagens antigas. Evite uma assinatura inventada incompatível com os produtores.

## 6. Exemplo genérico

Vulnerável como decisão de privilégio:
```typescript
const role = input.role;
```
Papel obtido de estado interno após identidade validada:
```typescript
const role = await roles.forUser(session.userId);
```

## 7. Limitações e verificação

O exemplo depende da confiabilidade da sessão e da consulta interna. Teste alteração dos dados, origem incorreta e falhas de verificação. Integridade não equivale a autorização para toda operação.
