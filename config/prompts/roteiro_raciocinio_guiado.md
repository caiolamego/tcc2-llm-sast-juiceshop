STATUS: APROVADO

# Roteiro de raciocínio guiado (estratégia P2)

Fonte: TCC 1, Seção 4.2.4 (`P2_raciocinio_guiado`). O roteiro abaixo reproduz as
etapas definidas no trabalho original. Qualquer alteração futura precisa ser
registrada como desvio do projeto pré-definido, com justificativa.

Texto de referência do TCC 1:

> O `P2_raciocinio_guiado` foi elaborado como uma forma estruturada de
> operacionalizar princípios associados ao Chain-of-Thought. Em vez de solicitar
> apenas uma resposta direta, o prompt orienta a LLM a decompor a análise em
> etapas explícitas: identificar a vulnerabilidade, explicar sua causa, descrever
> o impacto de segurança, propor uma correção no código e justificar tecnicamente
> por que a solução remove ou mitiga a vulnerabilidade. Essa abordagem busca
> induzir uma análise intermediária organizada, sem depender da exposição livre ou
> completa da cadeia de pensamento interna do modelo.

## Bloco a ser inserido no prompt

O texto abaixo é inserido entre o código e as restrições obrigatórias, em todas
as chamadas da estratégia P2. É o único bloco que distingue P2 de P1.

```
Antes de responder, percorra as cinco etapas abaixo, nesta ordem:

1. Identifique a vulnerabilidade presente no código.
2. Explique a causa da vulnerabilidade: que construção do código a torna
   possível e por quê.
3. Descreva o impacto de segurança: o que um atacante consegue obter ou fazer
   explorando essa falha.
4. Proponha a correção no código.
5. Justifique tecnicamente por que a solução proposta remove ou mitiga a
   vulnerabilidade identificada.
```

## Correspondência com os campos da resposta

O roteiro tem cinco etapas e o objeto de resposta tem seis campos (Decisão D3,
ADR-003). A correspondência é a seguinte:

| Etapa do roteiro | Campo da resposta |
|---|---|
| 1. Identificar | `vulnerabilidade_identificada` |
| 2. Explicar a causa | `causa_da_vulnerabilidade` |
| 3. Descrever o impacto | sem campo próprio; relatado dentro de `justificativa_tecnica` |
| 4. Propor a correção | `estrategia_de_correcao` e `edicoes` |
| 5. Justificar | `justificativa_tecnica` |
| — | `limitacoes_da_correcao` (acréscimo da D3, não previsto no roteiro do TCC 1) |

Duas observações para o Capítulo 4:

- A etapa 3 (impacto de segurança) não ganhou campo próprio porque o conjunto de
  campos veio da Seção 3.6 do TCC 1, não da 4.2.4. Manter o roteiro com cinco
  etapas preserva a fidelidade ao trabalho original; criar um sétimo campo agora
  alteraria o schema congelado.
- O campo `limitacoes_da_correcao` corresponde aos "possíveis cuidados
  adicionais" que o TCC 1 previa apenas para o `P4_rag_raciocinio_guiado`. Ele
  consta do schema para todas as estratégias, porque o schema é único (D3). Isso
  **não** torna P1 e P2 equivalentes a P4: o que distingue as estratégias é o
  conteúdo do prompt, não o formato da resposta.

## Congelamento

Este roteiro está congelado desde 2026-10-08, antes da execução E01. Nenhuma
alteração é feita com base em resultados da execução completa.