---
schema_versao: '1.0'
categoria: generico
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: Secure Code Review Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html
  consultado_em: '2026-10-13'
- titulo: Input Validation Cheat Sheet
  url: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

Um alerta estático identifica um padrão que precisa ser analisado no fluxo real. Comece pelo ponto indicado, pela regra e pelas dependências do comportamento.

## 2. Origem e condições

Localize origem dos dados, transformações, chamada final e controles anteriores. Separe fatos visíveis de hipóteses que exigem arquivos ou configuração ausentes.

## 3. Impactos e interpretação

Explicite qual capacidade do atacante seria necessária e qual efeito seria possível. Um padrão suspeito pode ser protegido ou inalcançável. Contexto documental não confirma vulnerabilidade.

## 4. Mitigação por mecanismo

### Análise
Verifique a semântica da API e a fronteira de confiança.
### Mudança mínima
Se houver risco sustentado pelo código, preserve a operação legítima e corrija o mecanismo. Não remova chamadas nem adicione comentários para esconder alertas.
### Evidência insuficiente
Descreva a limitação em vez de inventar causa ou requisitos; reanálise estática deve ser acompanhada de verificação funcional.

## 5. Preservação funcional

Preserve interfaces, mensagens, tratamento de erros e entradas válidas. Não introduza um requisito de negócio que não exista apenas para produzir um patch.

## 6. Exemplo genérico

Exemplo suspeito quando o valor pode não ser texto:
```typescript
return input.label.trim();
```
Quando o contrato exige texto, valide antes de preservar a operação:
```typescript
if (typeof input.label !== 'string') return existingFailure();
return input.label.trim();
```

## 7. Limitações e verificação

O exemplo trata tipos, não todas as vulnerabilidades. Se o tipo já é garantido, a checagem pode ser redundante. Verifique origem, caminhos de erro e requisitos antes de concluir pela correção.
