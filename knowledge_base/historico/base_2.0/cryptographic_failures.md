---
schema_versao: '1.0'
categoria: cryptographic_failures
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: Password Storage Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: Cryptographic Storage Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: Secrets Management Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

Algoritmos fracos, chaves previsíveis e segredos em código comprometem garantias criptográficas. O propósito importa: um hash para cache tem requisitos diferentes de senha ou autenticação.

## 2. Origem e condições

Identifique o dado protegido, a origem da chave, o adversário e como o resultado é verificado. Um valor público de teste pode não ser segredo; um literal de produção requer investigação do ciclo de vida.

## 3. Impactos e interpretação

Pode haver recuperação de credenciais, falsificação ou exposição de dados. O nome do algoritmo sozinho não demonstra um impacto: é preciso conhecer uso, parâmetros e alcance.

## 4. Mitigação por mecanismo

### Senhas
Use função especializada de derivação com salt e custo adequado, preferindo Argon2id quando disponível. Não use hash rápido como armazenamento de senha.
### Chaves e aleatoriedade
Obtenha segredos de armazenamento controlado; não adicione fallback embutido. Gere material imprevisível com API criptográfica.
### Dados cifrados
Use construção autenticada e gerenciamento correto de nonces e chaves; integridade e confidencialidade são garantias separadas.
### Rotação
Considere revogação, migração e permissões do segredo, além de removê-lo do arquivo.

## 5. Preservação funcional

Mantenha contratos de autenticação e compatibilidade dos dados existentes. Trocar algoritmo de senha exige leitura ou migração planejada dos hashes antigos; não compare texto puro.

## 6. Exemplo genérico

Exemplo vulnerável de configuração de segredo:
```typescript
const signingKey = 'shared-secret-example';
```
Configuração externa obrigatória, com erro sem revelar o valor:
```typescript
const signingKey = process.env.SIGNING_KEY;
if (!signingKey) throw new Error('Missing signing configuration');
```

## 7. Limitações e verificação

Variável de ambiente não substitui proteção operacional, rotação e controle de acesso. Teste configuração ausente, chave incorreta e migração. Não altere usos não secretos apenas para satisfazer um detector.
