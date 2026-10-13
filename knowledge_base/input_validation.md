---
schema_versao: '1.0'
categoria: input_validation
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: Input Validation Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: 'CWE-20: Improper Input Validation'
  url: https://cwe.mitre.org/data/definitions/20.html
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

Validação verifica estrutura e significado antes de usar dados. Tipos, faixas, obrigatoriedade e invariantes de negócio pertencem a níveis diferentes.

## 2. Origem e condições

Considere corpo, query, parâmetros, headers e dados persistidos externos. Verifique conversões: arrays, objetos e valores vazios podem ter semântica inesperada em APIs JavaScript.

## 3. Impactos e interpretação

Entradas inválidas podem causar erro, estado inconsistente ou abuso de operações. Uma validação ausente no trecho pode existir em middleware; examine a cadeia inteira.

## 4. Mitigação por mecanismo

### Estrutura
Aceite tipos e campos explícitos, limites e formatos coerentes; valide no servidor.
### Semântica
Verifique relações entre campos e transições permitidas. Um número bem formado ainda pode violar saldo, estoque ou ordem de etapas.
### Uso posterior
Validação não substitui autorização, parâmetros SQL ou encoding de saída. Não normalize silenciosamente valores cuja distinção tenha significado.

## 5. Preservação funcional

Preserve entradas válidas, incluindo zero quando permitido. Evite coerção implícita que modifica contratos. Campos opcionais e obrigatórios devem seguir o requisito existente.

## 6. Exemplo genérico

Vulnerável quando o estoque aceita apenas inteiros positivos:
```typescript
await inventory.reserve(input.quantity);
```
Validação antes da mesma operação:
```typescript
if (!Number.isSafeInteger(input.quantity) || input.quantity <= 0) return existingFailure();
await inventory.reserve(input.quantity);
```

## 7. Limitações e verificação

O limite superior e a disponibilidade exigem regras adicionais. Teste bordas, valores ausentes, strings, objetos e concorrência. Validação de forma não garante atomicidade.
