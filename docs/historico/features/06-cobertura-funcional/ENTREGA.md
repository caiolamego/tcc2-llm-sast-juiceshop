# Entrega — cobertura funcional dos 78 casos

Data: 17/10/2026. Implementação e auditoria concluídas; **a campanha completa
permanece pendente**. Não houve chamadas à LLM, commit, push ou campanha dos 78.
A configuração padrão foi preservada. Uso: [guia operacional](../../../cobertura_funcional.md).

## Resultado da revisão e da execução

| Informação | Resultado |
|---|---:|
| Ocorrências revisadas / arquivos | 78 / 46 |
| Revisões adequadas / insuficientes / pendentes | 63 / 15 / 0 |
| Casos com baseline comparável / sem seleção executável | 70 / 8 |
| Casos preparados / bloqueados | **52 / 26** |
| Grupos distintos executados | 39 |
| Testes aprovados / ignorados / falhos | 484 / 6 / 0 |
| Testes adicionais / controles que detectaram regressão | 3 grupos / 3 |

As 15 revisões insuficientes e a união de obrigações por arquivo bloqueiam 26
casos: dez outros casos em `server.ts` e um em `routes/order.ts` também precisam
das lacunas desses arquivos resolvidas. Um alerta adequado isoladamente não
dispensa as outras obrigações do arquivo alterado. Os 52 preparados possuem
baseline verificável no alcance declarado; não representam correções realizadas.
Os testes compartilhados foram executados uma vez por grupo, sem simular 78
avaliações independentes.

A [matriz completa](../../../../outputs/cobertura_funcional/COBERTURA_V1/cobertura_por_caso.csv),
a [matriz por arquivo](../../../../outputs/cobertura_funcional/COBERTURA_V1/cobertura_por_arquivo.csv)
e o [plano de lacunas](../../../../outputs/cobertura_funcional/COBERTURA_V1/plano_testes_adicionais.md)
registram as associações e seus limites.

## Componentes entregues

- Revisão autoral 1.0 e mapa derivado 2.0, reconciliados com as identidades do catálogo.
- Auditor independente, somente por leitura, com oito artefatos JSON/CSV/Markdown,
  publicação exclusiva e revalidação dos hashes das entradas.
- Política optativa `relacionada_v2`, contrato 4.0 e baseline funcional 2.0.
  Políticas anteriores continuam usando os contratos e critérios anteriores.
- Execução por grupos de servidor/API e Angular/Vitest/jsdom, com seleção explícita,
  JUnit, compilações próprias e ausência de fallback amplo.
- Staging exclusivo dos avaliadores adicionais e limpeza antes de SAST.
- Cache funcional vinculado à revisão, mapa, D, avaliadores, adaptadores, baseline
  e dependências instaladas de raiz/frontend. Cache SAST separado e comparação
  R/M sempre refeita para a ocorrência.
- Propagação pelo lançador/painel/ferramentas auxiliares; registros de domínios,
  grupos, testes esperados/executados/ignorados, compilações, tempos e baseline.
- Leitura de contrato 4.0 nas métricas e agrupamento por alcance funcional,
  preservando denominadores e a identificação histórica de registros antigos.

O preflight verifica prontidão e ambiente antes do cliente LLM e não executa
suítes funcionais. Após o patch, lacunas e ausência de evidência impedem F
positivo; falhas comprovadas ainda podem produzir F=0. R/M vêm do scan global
independentemente de F. Nenhum prompt, regra, catálogo, comparador ou critério
de parada foi alterado.

## Ambiente e baseline real

Checkout reservado: `workspace/wt-1`, K=1, commit
`f915bddd82790d0f3018902d36ae9b4241a5f51f`.
Python 3.12.3, Node 24.14.0, TypeScript 6.0.3,
Angular CLI/build 21.2.26, Vitest 4.1.11, jsdom 29.1.1, Semgrep 1.177.0.
As dependências existentes foram identificadas por conteúdo; não foram instaladas
dependências frontend em `wt-2`. `catalogo-alvo` permaneceu intacto.

[Baseline final](../../../../outputs/feature06/BASELINE_06/baseline_testes.json):
**143,442754 s**, incluindo compilações e seleções, excluindo a preparação inicial
das identidades de ambiente. Não é tempo por issue/prompt.

| Domínio | Grupos | Aprovados | Ignorados | Trabalho dos grupos |
|---|---:|---:|---:|---:|
| Servidor | 3 | 43 | 0 | 1,12 s |
| API | 28 | 341 | 6 | 58,04 s |
| Frontend | 8 | 100 | 0 | 66,60 s |

Compilação TypeScript da raiz: 2,84 s. Angular development/AOT: 9,22 s,
com saída temporária removida. Tempos de trabalho dos grupos não incluem toda
a preparação e não substituem a duração da sessão. Os seis ignorados não são
evidência executada de comportamento obrigatório.

Durante a investigação, o mesmo arquivo unitário de 35 testes publicou 23, 32 e
33 testes com `--test-force-exit` em três execuções; sem essa opção, publicou
35/35/35. Desabilitar cache TSX sozinho não resolveu a enumeração. A nova política
remove o force-exit somente dos unitários de servidor, preservando timeout e
conferência de identidades. APIs mantêm seu isolamento anterior. Veja o
[experimento controlado](../../../../outputs/feature06/INVESTIGACAO_NODE_01/resultados.json).
Isso é uma observação deste ambiente, sem reclassificar execuções antigas.

## Três grupos adicionais e controles

Os testes ficam em [tests/functional/juice_shop](../../../../tests/functional/juice_shop/).
Não são testes unitários Python e não entram nos prompts ou na base RAG.

| Grupo | Lacuna atendida | Controle deliberado |
|---|---|---|
| `insecurity_extra` | Contratos compartilhados de token/hash/cupom, seis casos | Token deluxe vazio perde a propriedade específica por usuário |
| `likes_extra` | Persistência do contador e identidade, três casos | Incremento zero deixa de preservar a contagem |
| `instructor` | Propriedade de configuração aninhada no frontend, um caso | Resolução para `undefined` quebra a correspondência normal do input |

Foi reservado o grupo frontend; os demais foram escolhidos pelo número de casos
que a lacuna compartilhada desbloqueia. A revisão de `server.ts` exige vários
comportamentos e não fica suficiente com uma única correção isolada. Os grupos
existentes não foram duplicados. Os três testes detectaram os mutantes e os
arquivos originais foram restaurados: [evidência dos controles](../../../../outputs/feature06/CONTROLES_04/resultado_controles.json).

## Conjunto D e limitações restantes

O [D versionado](../../../../config/conjunto_d_cobertura_v1.json) preserva integralmente
as 75 entradas anteriores. Foram revisadas 33 asserções Angular candidatas:
observam mocks ou estado de UI e não satisfazem os critérios atuais para D.
Portanto, **zero adições Angular**, com razões e hashes registrados. Não se
transformou um teste em D somente por conter payload malicioso.

As lacunas incluem inicialização/modelos compartilhados em `server.ts`, extração
de marcadores de desafios, chat, TOTP de dados estáticos, empacotamento,
CAPTCHA aritmético, extração ZIP, desconto efetivo de campanha, interpretação das
legendas e avaliação independente dos próprios `.spec.ts` alvo.

O CAPTCHA de imagem da exportação não testa o CAPTCHA aritmético de feedback.
Consumir a resposta fornecida pelo próprio endpoint não demonstra a equivalência
matemática da expressão. O teste de campanha existente termina em `assert.ok(true)`;
não demonstra o desconto final. Upload PDF não demonstra extração ZIP. Entregar
HTML não demonstra execução do parser de legendas. Essas associações próximas
foram mantidas como evidência parcial, com cobertura insuficiente.

Angular/jsdom e mocks não equivalem a navegador real, integração completa ou
ausência de XSS. Certos testes existentes exigem detalhes da implementação que
uma correção legítima pode modificar; a separação F/D atual foi preservada e essa
possibilidade permanece uma ameaça à validade. Nenhum novo navegador/Cypress foi
introduzido. A cobertura é delimitada pelas asserções declaradas, não por um
percentual inventado de linhas ou pela simples ausência de falhas.

## Reprodução

Executar da raiz, sempre com destino novo:

```bash
make test-unit PYTHON=.venv/bin/python

.venv/bin/python scripts/experiment/validate_functional_coverage.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 \
  --mapa-testes config/mapa_testes_relacionados_v2.yaml \
  --revisao config/cobertura_funcional_v1.yaml \
  --saida outputs/feature06/NOVO_BASELINE
```

O mesmo comando com `--controles` e outra saída executa os controles.
A auditoria e o exemplo preflight estão no [guia de comandos](../../../cobertura_funcional.md).
Uma mudança da revisão, avaliadores ou adaptadores exige regenerar baseline/mapa
e usar saída de execução compatível. Não sobrescrever os artefatos entregues.

A validação unitária inicial passou em 236 testes e a final em 258. Uma chamada
ao Makefile fora da `.venv` encontrou dependências Python ausentes (`dotenv`);
a execução oficial acima usou a `.venv` e passou. Não foi necessário instalar
dependências no Python global.

## Preflight e métricas sem LLM

O [AMP_COV_PREFLIGHT_03](../../../../outputs/feature06/AMP_COV_PREFLIGHT_03/preflight.json)
validou login, keyServer, um caso de `lib/insecurity.ts` e o helper frontend:
quatro casos, oito prompts P1/P2, K=1, contrato 4.0, custo de API zero.
O gate SAST reproduziu os 78 alertas sem ocorrências ausentes/adicionais;
conservou oito diagnósticos preexistentes de parsing. A compilação Angular real
não elimina essas limitações do parser SAST.

A [consolidação](../../../../outputs/feature06/AMP_COV_PREFLIGHT_03_METRICAS/metricas.json)
verificou o snapshot portátil de cobertura/baseline e registrou zero tentativas,
métricas de remediação nulas e CSV de cobertura com cabeçalho. Isso valida
preparação e leitura de evidências, sem constituir piloto de correções.

Comando completo usado, sem chamadas à LLM:

```bash
.venv/bin/python src/pipeline/run_pipeline.py \
  --execucao AMP_COV_PREFLIGHT_03 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --perfil-sast config/perfis/ampliado_piloto_v1/perfil.json \
  --saida outputs/feature06/AMP_COV_PREFLIGHT_03 \
  --casos AMPfb154534099cb3ca,AMP95adf572d3c6677f,AMP41302bd0fb784039,AMPd53a8fdb9fb5d682 \
  --estrategias P1,P2 --k 1 --semgrep-bin .venv/bin/semgrep \
  --baseline-testes outputs/feature06/BASELINE_06/baseline_testes.json \
  --politica-validacao relacionada_v2 \
  --mapa-testes config/mapa_testes_relacionados_v2.yaml \
  --cobertura-funcional config/cobertura_funcional_v1.yaml --somente-preflight

.venv/bin/python scripts/reports/consolidate_metrics.py \
  --execucao AMP_COV_PREFLIGHT_03 \
  --entrada outputs/feature06/AMP_COV_PREFLIGHT_03 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --saida outputs/feature06/AMP_COV_PREFLIGHT_03_METRICAS --definicao-f criterio
```

Esses destinos já existem: para repetir, trocar identificação e saída, ou usar o
exemplo do lançador que cria identificações novas automaticamente.

## Integridade e verificações finais

Os hashes e resultados consolidados estão em
[verificacao.json](../../../../outputs/feature06/verificacao.json), incluindo regressão
unitária, prontidão, controles, comparação determinística e limpeza dos checkouts.
O manifesto da auditoria contém os hashes completos das entradas e das oito saídas.

| Entrada | SHA-256 |
|---|---|
| Revisão | `992ee8f701b02da1f1b02d6285d1a35e76655f3eba5e8951919a51bb61f4fd5a` |
| Mapa 2.0 | `0166f0517aa77496bdfbb6e4ff83b147104df11a4c88fc090ae602a429ba1d17` |
| D versionado | `a9da519bb2e02d6c92179f4cc71ab642e7ce44b0dab09f2c7b5022bfd9b042fd` |
| Baseline final | `af15ab686ca7539e9f663528227aa5c323d634de170ac2760e66ffd1c501b34b` |

Preparações intermediárias desta entrega foram preservadas em `.cache`, separadas
dos artefatos oficiais. Os resultados anteriores à feature não foram movidos.
O piloto com LLM e a campanha completa permanecem para uma entrega posterior.
