---
schema_versao: '1.0'
categoria: concurrency
versao_documento: '1.0'
status: PRONTO
fontes:
- titulo: 'CWE-362: Race Condition'
  url: https://cwe.mitre.org/data/definitions/362.html
  consultado_em: '2026-10-13'
- titulo: 'Sequelize v6: Transactions'
  url: https://sequelize.org/docs/v6/other-topics/transactions/
  consultado_em: '2026-10-13'
---
## 1. Descrição e sinais

Condição de corrida aparece quando operações concorrentes observam e alteram estado compartilhado sem preservar uma invariante. Uma sequência de `await` não fornece exclusão entre requisições.

## 2. Origem e condições

Localize o estado compartilhado e a distância entre verificar e usar. Considere múltiplos processos e workers; um mutex em memória não coordena todos os servidores.

## 3. Impactos e interpretação

Podem ocorrer reservas duplicadas, saldo inconsistente ou atualização perdida. A presença de operações assíncronas não prova corrida: o armazenamento pode fornecer atomicidade.

## 4. Mitigação por mecanismo

### Atualização atômica
Expresse condição e alteração na mesma operação do armazenamento quando possível e confira linhas afetadas.
### Transações
Agrupe operações dependentes e use isolamento ou bloqueios adequados. Uma transação gerenciada faz commit/rollback, mas seu uso sozinho não impede toda corrida.
### Coordenação
Escolha bloqueio ou versão otimista com escopo adequado; defina repetição limitada e evite manter locks durante operações externas lentas.

## 5. Preservação funcional

Preserve disponibilidade e respostas do fluxo legítimo. Não serializar tudo sem necessidade. Qualquer retry deve considerar idempotência, falhas e efeitos já produzidos.

## 6. Exemplo genérico

Exemplo vulnerável de reserva em armazenamento abstrato:
```typescript
if (await stock.available(itemId) > 0) await stock.decrement(itemId);
```
Contrato de armazenamento com condição e alteração atômicas:
```typescript
const reserved = await stock.decrementIfPositive(itemId);
if (!reserved) return existingFailure();
```

## 7. Limitações e verificação

A API atômica ilustrada precisa de implementação e garantia no armazenamento real. Teste requisições simultâneas, rollback e repetição. Não conclua atomicidade a partir do nome de uma função.
