# Feature 04 — Métricas e consolidação dos resultados

**Status:** implementada e validada offline; [evidências de entrega](ENTREGA.md).  
**Data:** 13/10/2026.  
**Dependências:** features [01](../01-catalogo-ampliado/ENTREGA.md), [02](../02-integracao-catalogo/ENTREGA.md) e [03](../03-rag-prompts/ENTREGA.md).  
**Objetivo:** preparar cálculos verificáveis e relatórios reproduzíveis antes do piloto de correções reais.

## 1. Problema e resultado esperado

O pipeline já registra tentativas com R/F/M, classificação, estratégia, custos e artefatos. O script `scripts/reports/metricas_execucao.py` calcula parte das métricas, mas ainda não existe uma camada reutilizável em `src/pipeline/metrics/`, exportação CSV completa ou consolidação das dimensões do catálogo ampliado.

Esta feature organiza e completa a análise, usando registros existentes e fixtures de resultados conhecidos. Não executa correções reais. O preflight da feature 03 contém 312 prompts, mas nenhum resultado de remediação: esses prompts não são 312 tentativas de correção.

A entrega deve produzir JSON e CSV rastreáveis, declarar os denominadores, separar simulações de resultados reais e preservar os relatórios anteriores. Após o aceite, o piloto poderá verificar geração, aplicação, validação e análise em conjunto.

## 2. Referencial e estado atual

Fontes locais de autoridade:

- [TCC1](../../../TCC1___Caio_Lamego_e_Matheus_Brant-11.pdf), §3.9, pp. 43–44: TRV, TRI, TPF, TNINI, TFF e RRIS; `m` representa tentativas realizadas.
- [Protocolo experimental](../../docs/protocolo_experimental.md), seção de integração ampliada: resultados indeterminados e denominadores medidos.
- [Guia de continuidade](../../docs/GUIA_CONTINUIDADE_TCC2.md), entrega G: consolidação, agregações e aplicação conjunta para RRIS.
- [Calculador existente](../../scripts/reports/metricas_execucao.py): comportamento histórico a preservar.

| Componente | Situação verificada antes desta feature |
|---|---|
| TRV, TRI, TPF, TNINI, TAP | Implementadas no script atual |
| Separação P1L | Implementada; diagnóstico reportado à parte |
| Três definições de F | `sem_separacao`, `marcador`, `criterio` |
| Custos, tokens e cache | Cálculo parcial disponível |
| TCD | Indicador exploratório baseado em falhas de testes classificados como D |
| TFF | Ainda não exportada pelo calculador atual |
| CR/TRV por caso | Há taxa por casos observados; falta explicitar o conjunto solicitado e a cobertura |
| TRV-P | Prevista no README; sem política de pesos implementada/verificada |
| RRIS | Prevista; falta evidência de aplicação conjunta de patches aceitos |
| CSV e agregações ampliadas | Pendentes |
| `src/pipeline/metrics/` | Ausente |

O histórico utiliza denominador total também nas taxas auxiliares. O modo ampliado atual calcula TRI/TPF/TNINI somente sobre os valores medidos. Essa diferença deve permanecer explícita; não reescrever relatórios para aparentar equivalência metodológica.

## 3. Escopo

### Incluído

- Extração da lógica reutilizável de carregamento, normalização, cálculo e exportação.
- Compatibilidade das funções e do comando histórico de métricas.
- Consolidação verificável dos modos histórico e ampliado, incluindo contratos 1.0 e 2.0.
- TRV, TRI, TPF, TNINI, TFF e TAP; cobertura por caso e tratamento de pendências.
- Relatórios por estratégia, caso, CWE, OWASP, severidade, regra e auditoria.
- Separação de desenho, P1L, dry-run, cache e execuções sem tentativas.
- Custos e tempos conhecidos, com indicação de completude.
- Leitura/cálculo de RRIS a partir de evidência conjunta externa válida.
- TRV-P opcional, somente com política de pesos explícita e completa.
- Testes com resultados esperados calculados manualmente e validação sobre cópias dos arquivos oficiais.

### Fora desta feature

- Chamadas à LLM, instalação de dependências ou execução de novos experimentos.
- Aplicar patches, resolver conflitos, executar SAST ou testes do Juice Shop.
- Gerar a evidência conjunta necessária à RRIS: procedimento posterior ao piloto.
- Alterar F/D, prompts, RAG, catálogos, regras ou contratos científicos existentes.
- Confirmar vulnerabilidades a partir da classificação da auditoria ou da remoção de alertas.
- Criar gráficos ou dashboard como condição de aceite; JSON/CSV são a entrega principal.
- Alterar `.gitignore`, fazer commit ou push automático.

RRIS pode estar `null` na entrega real porque não há aplicação conjunta comprovada. O leitor e a fórmula devem ser testados com fixtures completas; ausência de evidência não bloqueia as demais métricas nem autoriza inventar um resultado.

## 4. Arquitetura proposta

```text
src/pipeline/metrics/
├── __init__.py
├── loader.py           leitura, identidade e proveniência
├── normalizer.py       registros antigos/novos e definições de F
├── calculator.py       funções puras e denominadores
├── exporter.py         JSON/CSV determinísticos
└── rris.py             validação e leitura de evidência conjunta

scripts/reports/
├── metricas_execucao.py      interface histórica preservada
└── consolidate_metrics.py   nova interface com publicação protegida

tests/unit/
└── test_metrics.py
```

Criar módulos com funções efetivas, sem arquivos vazios para completar a árvore. Usar biblioteca padrão e os loaders existentes; não introduzir pandas, serviço externo ou acesso de rede.

Preservar imports públicos já usados nos testes, como `indices`, `normalizar` e `custos` do script atual, delegando para a lógica extraída. A interface antiga mantém resultados e política histórica. Novas métricas e campos pertencem ao relatório versionado novo.

## 5. Entradas, identidade e proveniência

A entrada é um diretório de execução ou a raiz histórica que contém:

```text
resultados_consolidados/execucoes.jsonl
resultados_consolidados/<EXECUCAO>_sessoes.json   # opcional
contrato_execucao.json                         # obrigatório no modo ampliado
```

O catálogo correspondente é selecionado explicitamente. No modo ampliado, conferir hashes do catálogo, exclusões e metadados contra o contrato. Conferir contrato das linhas e hashes dos artefatos conforme a feature 02, sem executar seu preflight.

Regras de leitura:

1. Ler o JSONL inteiro e falhar em JSON truncado/corrompido; não descartar linhas silenciosamente.
2. Selecionar a execução solicitada. Outras execuções do mesmo arquivo histórico não entram nos cálculos.
3. Rejeitar IDs duplicados, casos ausentes do catálogo, identidade divergente, contratos misturados e valores R/F/M fora de `0`, `1` ou `null`. Rejeitar booleanos como substitutos numéricos no schema novo.
4. Usar `caso_id` e `estrategia_prompt`/`condicao` como campos estruturados. Nomes de arquivos não são a fonte principal da estratégia. Registros antigos podem usar parser compatível documentado; não depender de posição fixa em IDs com underscores.
5. No modo ampliado, verificar o conjunto de casos solicitado no contrato. Não presumir que toda execução selecionou os 78 casos.
6. No histórico sem contrato, declarar proveniência limitada. Artefato ausente não é reconstituído nem ignorado como se estivesse verificado: listar a lacuna e limitar o resultado correspondente.
7. Não modificar as entradas. Nenhuma normalização é gravada sobre os registros oficiais.

Campos do catálogo enriquecem os relatórios: CWE, OWASP, severidade, `categoria_rag`, regra e classificação da auditoria. Nos registros RAG, manter também a categoria efetivamente recuperada. Não filtrar falsos positivos, inconclusivos ou metadados ausentes.

## 6. Unidades, população e regra de parada

Distinguir explicitamente:

- **Tentativa:** registro de uma execução caso/estratégia; tem identidade própria.
- **Caso:** ocorrência catalogada, com identidade histórica ou ampliada.
- **Execução:** conjunto solicitado, contrato e sessões correspondentes.
- **Alerta global:** finding da reanálise, usado na RRIS.
- **Desafio:** referência dinâmica; não equivale a caso ou tentativa.

A população principal reúne tentativas reais do desenho P1–P4 da execução selecionada. P1L e dry-run são relatórios separados. Respostas reutilizadas do cache podem compor os resultados das tentativas, mas não são novas gerações independentes nem novas cobranças.

A cadeia observada respeita a primeira tentativa aceita: estratégias posteriores podem não ter sido executadas. Não criar linhas P2/P3/P4 fictícias para casos aceitos antes. Registrar o número de casos que chegaram a cada estratégia.

Se houver registros posteriores a um aceite, identificá-los como pós-aceite e reportá-los à parte; não apagá-los. Réplicas independentes exigem identidade e desenho explícitos, não escolha automática da melhor tentativa. Duplicatas de caso/estratégia sem explicação devem falhar.

As análises de sensibilidade pelas três definições de F usam apenas evidências observadas. Parada retrospectiva sob outra definição não permite inferir os resultados de estratégias que nunca rodaram. Preservar a visão histórica do script antigo como retrospectiva, com incompletude declarada.

## 7. Fórmulas e denominadores

Definição principal de F: `criterio`, mantendo as outras duas como sensibilidade. Não reclassificar a auditoria nem alterar a regra de aceite nesta feature.

Para uma população de `m` tentativas, seja `A_j = 1` quando o patch foi aplicado e R, F e M são comprovadamente 1; nos demais estados, `A_j = 0` para a contagem de remediações validadas. Essa contagem não transforma valores desconhecidos em medições negativas.

| Métrica | Fórmula | Denominador e interpretação |
|---|---|---|
| TRV | `Σ A_j / m` | Todas as tentativas da população; indeterminadas e não aplicadas permanecem no denominador |
| TRI | `Σ R_j / n_R` | Ampliado: somente R medido; histórico: comportamento original com `m` |
| TPF | `Σ F_j / n_F` | Ampliado: somente F medido; histórico: comportamento original com `m` |
| TNINI | `Σ M_j / n_M` | Ampliado: somente M medido; histórico: comportamento original com `m` |
| TFF | `1 − TPF` | Mesmo denominador e política de TPF; no ampliado, taxa de falha entre medições de F |
| TAP | `aplicadas / m` | Aplicação de patch, independentemente de aceite |
| CR / TRV por caso | `casos com algum aceite / casos solicitados` | Identidade por ocorrência; não chamar de vulnerabilidades comprovadamente corrigidas |
| RRIS | `(I_antes − I_depois) / I_antes` | Findings globais de uma aplicação conjunta comprovada |

Preservar a diferença para o TCC1: suas taxas auxiliares usam `m` comum e variáveis binárias. No modo ampliado, a política posterior usa denominadores medidos por admitir indeterminação. Exportar também as proporções mínimas `TRI_minima`, `TPF_minima`, `TNINI_minima = sucessos comprovados / m`, como análise suplementar, sem apresentá-las como medições negativas dos desconhecidos. Não definir `1 − TPF_minima` como falha funcional comprovada.

Cada métrica exporta valor, numerador, denominador, política e motivo de indisponibilidade. Calcular com precisão completa e arredondar somente na exportação: seis casas decimais no schema novo. O comando legado preserva seu arredondamento atual.

Quando o denominador é zero, usar `null` e motivo `sem_denominador`. Não representar ausência de tentativas como taxa zero. Para preflight sem JSONL e com relatório próprio válido, publicar `status=sem_tentativas`, métricas de remediação nulas e contagem de prompts em seção de preparação separada. JSONL inesperadamente ausente numa execução de correções é erro.

### Casos e cobertura

Exportar casos solicitados, iniciados, aceitos, sem aceite e pendentes/interrompidos. Um caso sem registro não é uma tentativa fracassada. Casos resolvidos antes de P4 não estão pendentes.

No histórico sem conjunto solicitado verificável, calcular somente `TRV_caso_observado` sobre casos presentes e deixar CR do conjunto solicitado nula. Não inventar que os 12 casos históricos foram todos solicitados em qualquer execução.

### Indeterminação e falhas

Separar `R/M` indeterminados, F não medido, normalização histórica incompleta, patch não aplicado, falha técnica e interrupção. Essas contagens podem se sobrepor; explicitar que não formam automaticamente uma partição.

Não aceitar automaticamente uma linha com R/F/M nulos. Contradições entre dados e classificação de aceite no schema ampliado são erros de dados. No histórico, inferências retrospectivas devem ser identificadas e nunca sobrescrever a classificação original.

### TCD e confirmação dinâmica

Preservar o indicador exploratório atual em uma seção separada. Informar quantas tentativas aceitas derrubaram testes marcados como D e qual é o denominador. Falha de teste D isolada não prova bloqueio do ataque: exige excluir falha de infraestrutura e conferir a evidência pertinente.

Não tratar desafios sem teste como falhas ou sucessos dinâmicos. Não utilizar contagem de desafios como denominador de remediação por caso.

### TRV-P opcional

Não inventar pesos de severidade. Sem política fornecida, retornar `null`, motivo `politica_pesos_ausente`. Se habilitada, exigir configuração versionada com pesos finitos positivos para todas as severidades presentes, hash da política e aliases explícitos. Severity ausente/sem peso impede essa métrica, sem impedir as não ponderadas.

A fórmula é `Σ(w_j × A_j) / Σ w_j`. Esse indicador é complementar do README, não uma fórmula prevista no §3.9 do TCC1. Nenhuma alteração de pesos deve ser feita depois dos resultados apenas para favorecer uma conclusão.

## 8. Estratégias e agregações

Gerar visão geral e agregações por estratégia, caso, CWE, OWASP, severidade, regra, classificação da auditoria e categoria original/recuperada de RAG.

Para múltiplas CWEs, o agrupamento principal usa o conjunto normalizado como chave composta, sem duplicar a tentativa em vários grupos. Uma visão opcional por cada CWE deve declarar sobreposição; seus totais não podem ser somados como se fossem exclusivos.

Preservar `null` nos metadados. Rótulos como `SEM_OWASP` são somente de apresentação, não reclassificação. Agrupar valores ausentes em um grupo visível, mantendo-os nos totais.

P2 recebe casos não resolvidos por P1, e assim sucessivamente. Taxas por estratégia descrevem conjuntos diferentes; exportar casos alcançados e registrar essa seleção. Não interpretar diferença bruta como comparação causal entre estratégias.

## 9. Custos, tokens e tempos

- Separar chamadas reais registradas, usos do cache e simulações.
- Somar custo de novas chamadas registradas uma vez; não cobrar novamente o custo histórico presente em uma linha de cache.
- Contabilizar tokens de novas chamadas separadamente dos tokens associados a respostas reutilizadas.
- Reportar latência LLM, duração SAST, validação e duração de sessão quando disponíveis.
- Não somar durações de workers paralelos como se fossem duração total de parede.
- Não inferir custo zero para chamadas cujo registro ficou incompleto ou valor está ausente. Exportar custo conhecido, valores ausentes e `completude`.
- Resultados a partir de JSONL não demonstram todas as chamadas que poderiam ter falhado antes do registro. Explicitar o limite; sessões/erros ajudam a identificar lacunas, mas não inventar cobranças.

## 10. Contrato de RRIS

O consolidado aceita opcionalmente um manifesto `--evidencia-rris`, produzido por procedimento posterior de aplicação conjunta. Nesta feature, o comando apenas lê e valida essa evidência.

Contrato mínimo do manifesto de evidência, schema `1.0`:

- Execução de origem, commit baseline, hashes do catálogo e perfil SAST.
- Definição de F usada para selecionar os aceites.
- IDs das tentativas aceitas e hashes dos patches efetivamente selecionados.
- Ordem de aplicação; tentativas não aplicadas e conflitos identificados.
- Caminhos relativos e hashes dos scans globais antes/depois, com mesmo perfil, versão e escopo.
- Resultado funcional do conjunto aplicado, com hash do artefato pertinente.
- Diagnósticos, timeout/falhas operacionais e política de cobertura.

Rejeitar paths que escapem da raiz da evidência, symlinks externos, hashes adulterados, perfil/commit incompatíveis e patch selecionado sem aceite comprovado. Não deduzir as contagens somando R de tentativas isoladas.

Se não houver evidência: `RRIS=null`, motivo `evidencia_conjunta_ausente`. Se `I_antes=0`: nula por ausência de denominador. Diagnósticos que impeçam comparabilidade tornam RRIS indeterminada; avisos idênticos em arquivos não alterados podem conservar o cálculo com cobertura limitada conforme a política da feature 02.

RRIS pode ser negativa se a evidência conjunta válida mostrar mais findings depois; não limitar a zero. O relatório identifica exatamente os patches aplicados e conflitos, e não chama um conjunto funcionalmente reprovado de remediação conjunta validada. Redução estática, quando comparável, pode ser reportada separadamente do aceite funcional conjunto.

A implementação deste leitor não significa que a aplicação conjunta ou o experimento final já ocorreram.

## 11. CLI e publicação

Interface implementada:

```bash
.venv/bin/python scripts/reports/consolidate_metrics.py \
  --execucao AMP_DRY_01 \
  --entrada outputs/feature02/AMP_DRY_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --saida outputs/feature04/AMP_DRY_01_METRICAS_NOVA \
  --definicao-f criterio
```

Argumentos obrigatórios: `--execucao`, `--entrada`, `--catalogo`, `--saida`. Opcionais: `--definicao-f` (padrão `criterio`), `--evidencia-rris`, `--politica-pesos`. Exportar as três definições de F; o argumento identifica a principal.

O relatório contém seções separadas para real/desenho, dry-run e diagnóstico. Não oferecer modo que misture simulações com remediação real. Uma execução apenas dry-run permanece identificada como validação operacional.

Usar bootstrap e caminhos ancorados existentes. Argumentos relativos explícitos resolvem contra o diretório corrente. `--help` funciona sem checkout, `.env`, API ou Semgrep instalado.

Publicar em diretório novo, recusando destino existente inclusive vazio, sobreposição com entradas e diretórios históricos. Reservar com lock exclusivo e escrever em temporário irmão antes da promoção. Não oferecer `--force`. Limpar somente temporários/lock da própria execução em falhas; preservar lock alheio.

Revalidar hashes das entradas antes da publicação. Serialização determinística sem timestamp de geração ou caminhos absolutos. JSON UTF-8 com chaves ordenadas, indentação e newline final. CSV UTF-8, cabeçalho fixo, ordem estável, newline `\n`, quoting padrão e campos nulos vazios, acompanhados de colunas de status/motivo quando necessário.

Códigos de saída: `0` sucesso, `2` argumentos inválidos, `1` erro de dados/execução. O comando legado continua disponível e não é executado automaticamente sobre as saídas históricas durante a validação.

## 12. Artefatos novos

```text
<saida>/
├── metricas.json
├── tentativas.csv
├── casos.csv
├── metricas_gerais.csv
├── metricas_por_estrategia.csv
├── metricas_por_cwe.csv
├── metricas_por_owasp.csv
├── metricas_por_severidade.csv
├── metricas_por_regra.csv
├── metricas_por_auditoria.csv
├── metricas_por_rag.csv
└── manifesto.json
```

`metricas.json`, schema `1.0`, contém identificação, população, definição principal, políticas/denominadores, cobertura, resultados das três definições, agregações, custos/tempos, RRIS, avisos e proveniência. Preflight recebe seção própria de preparação com métricas de remediação indisponíveis.

`tentativas.csv` preserva ID, caso, condição, estratégia, dry-run/cache, dados originais e normalizados, R/F/M das três definições, aplicação, classificação, metadados do catálogo/RAG, custos e tempos. Diferenciar dado observado de inferência histórica.

`casos.csv` reconcilia o conjunto solicitado com casos iniciados, aceitos e pendentes; inclui estratégia de aceite e motivo de indisponibilidade. Dados pessoais ou respostas completas da LLM não são necessários nesses CSVs.

Os CSVs agregados incluem execução, população, definição F, grupo, métrica, valor, numerador, denominador, política, status e motivo. Não exportar só porcentagens sem base de cálculo.

O manifesto registra schema, execução, hashes das fontes e contratos, políticas de cálculo/normalização/exportação, configurações opcionais e hashes dos artefatos gerados. Não contém auto-hash, duração de processamento nem paths absolutos. Conteúdo muda apenas com entradas ou políticas relevantes.

## 13. Exemplos de aceite numérico

Fixture ampliada com quatro tentativas do desenho:

| Tentativa | Aplicação | R | F | M | Resultado |
|---|---|---:|---:|---:|---|
| T1 | aplicado | 1 | 1 | 1 | aceita |
| T2 | aplicado | 0 | 1 | 1 | rejeitada |
| T3 | aplicado | null | 0 | null | indeterminada SAST |
| T4 | não aplicado | null | null | null | não aplicada |

Resultados esperados para a definição escolhida:

- `m=4`, aceitas `1`, `TRV=1/4`, `TAP=3/4`.
- `n_R=2`, `TRI=1/2`; `n_F=3`, `TPF=2/3`, `TFF=1/3`.
- `n_M=2`, `TNINI=2/2`.
- Proporções mínimas: `TRI_minima=1/4`, `TPF_minima=2/4`, `TNINI_minima=2/4`.
- Valores nulos das linhas permanecem nulos no CSV; T4 não demonstra falha funcional.

Outras fixtures: conjunto solicitado de cinco casos com dois aceites e um ainda sem tentativa → CR `2/5`, cobertura iniciada explicitada; evidência RRIS com dez findings antes e sete depois → `3/10`; ausência de evidência → RRIS nula.

O dry-run oficial de dois casos tem R/F/M `0/1/1` e `0/0/1`. No bloco de simulação: TRV `0`, TRI `0`, TPF `1/2`, TFF `1/2`, TNINI `1`, TAP `1`. A população real fica vazia, com taxas reais nulas e custo conhecido zero. Esse resultado não é evidência de eficácia da LLM.

## 14. Testes obrigatórios

- [x] Fórmulas acima conferidas por resultados esperados independentes do código.
- [x] Denominadores total/medido e diferença histórica/ampliada explícitos.
- [x] Vazio, preflight sem tentativas, apenas dry-run e apenas diagnóstico.
- [x] Separação de P1L, cache, simulações e chamadas reais.
- [x] Cadeia interrompida por aceite, estratégias não alcançadas e pós-aceite.
- [x] Casos solicitados sem registros, interrompidos e catálogo parcialmente selecionado.
- [x] Normalização histórica incompleta, metadados ausentes e múltiplas CWEs.
- [x] JSONL truncado, duplicatas, estratégia inválida, contradição de aceite e valores inválidos.
- [x] Contratos 1.0/2.0, hashes adulterados e artefatos ausentes/proveniência limitada.
- [x] TFF com F desconhecido; ausência de medição não vira falha funcional.
- [x] Custos ausentes, cache repetido e tempos paralelos versus duração de sessão.
- [x] TRV-P sem configuração, pesos inválidos/incompletos e configuração completa.
- [x] RRIS ausente, zero findings antes, valor negativo, conflitos e cobertura limitada/indeterminada.
- [x] RRIS não é soma dos aceites; exige hashes e evidência conjunta comparável.
- [x] CSV preserva Unicode, vírgulas, aspas, listas e valores nulos.
- [x] JSON/CSV determinísticos entre diretórios diferentes.
- [x] Saída existente, lock concorrente, falha de escrita e alteração da entrada durante geração.
- [x] CLI de outro diretório; `--help` sem serviços/dependências do alvo.
- [x] Compatibilidade dos imports e cálculos históricos já usados no projeto.
- [x] Nenhum teste chama LLM, Semgrep, aplica patches ou executa testes funcionais do alvo.

## 15. Validação com arquivos oficiais

1. Capturar hashes dos relatórios/registros históricos e fontes congeladas antes de editar código.
2. Executar testes existentes e registrar falhas preexistentes.
3. Testar a normalização de E01/E02 e a reprodução dos campos já calculados em cópias temporárias. Não regenerar os JSONs oficiais no lugar.
4. Consolidar `AMP_DRY_01` em saída nova e conferir os valores da seção 13 e a segregação da simulação.
5. Consolidar o preflight `AMP_RAG_PREFLIGHT_01` em saída nova: 78 casos, 312 prompts, zero tentativas; taxas de remediação nulas.
6. Gerar novamente em outro diretório novo e comparar todos os artefatos byte a byte.
7. Conferir somas, cobertura e denominadores de todas as agregações.
8. Executar `make test-unit PYTHON=.venv/bin/python`.
9. Conferir hashes históricos, links locais e `git diff --check`.

As ausências históricas devem ser reportadas; não declarar proveniência integral se faltarem artefatos. Validação completa do relatório ampliado exige os artefatos que seu contrato referencia.

## 16. Documentação e critérios de conclusão

- [x] Módulos e CLI nova implementados; comando/imports legados preservados.
- [x] Fórmulas, denominadores e política de desconhecidos documentados e testados.
- [x] JSON/CSV reconciliados com as entradas e publicação sem sobrescrita.
- [x] Simulações e preparação separadas das métricas reais.
- [x] Relatórios oficiais de validação gerados em saídas novas e reproduzíveis.
- [x] RRIS e TRV-P indisponíveis têm motivos explícitos; leitores opcionais testados.
- [x] Testes passando e evidências históricas intactas.
- [x] README, protocolo, índice de features e guia atualizados somente com verificações concluídas.
- [x] `ENTREGA.md` registra ambiente, comandos, versões, hashes, exemplos numéricos, comparação determinística e limites.

O aceite desta feature significa que os cálculos estão prontos e verificados. Não significa que já existem resultados reais das quatro estratégias no conjunto ampliado.

## 17. Continuidade

Após a entrega, especificar o piloto de remediação: casos contrastantes, orçamento, modelo/configurações, parâmetros congelados e cobertura funcional/dinâmica. O piloto validará também a consolidação automática das tentativas reais.

A aplicação conjunta dos patches aceitos, conflitos, validação funcional global e geração da evidência de RRIS pertencem a um procedimento posterior explicitamente identificado. Os registros atuais de aceites isolados não substituem esse procedimento.

As alterações desta especificação e da implementação futura permanecerão locais, sem commit, push ou chamadas à LLM automáticos.


## 18. Resultado da implementação

A entrega passou em 153 testes (115 iniciais + 38 novos). Os relatórios finais estão em `outputs/feature04/AMP_DRY_01_METRICAS_V2/` e `outputs/feature04/AMP_RAG_PREFLIGHT_01_METRICAS_V2/`; `V2` identifica a segunda publicação local de validação, mantendo schema/política 1.0. As publicações V1 intermediárias foram preservadas e não são as referências finais de aceite.

Cada relatório contém 13 artefatos. Foram comparados byte a byte com nova geração em diretório temporário. Os resultados E01/E02 foram reproduzidos em cópias, preservando todos os campos científicos arquivados. RRIS real continua indisponível por ausência de aplicação conjunta; TRV-P, por ausência de política de pesos.

Foi encontrada divergência preexistente em `config/perfis/ampliado_v1/regras_remotas.yaml`. Recuperou-se do Git um snapshot exato das regras congeladas em `outputs/feature04/preparacao/perfil_sast/`, sem mudar o arquivo atual ou os contratos. O leitor valida o snapshot pelo hash, registra a divergência e revalida os arquivos antes da publicação. Veja a [entrega](ENTREGA.md).

### Snapshots do perfil

O leitor procura primeiro `<entrada>/perfil_sast/perfil.json`, se presente; um snapshot local inválido é erro. Sem snapshot local, procura manifests por hash em `config/perfis/*/perfil.json` e `outputs/feature*/preparacao/perfil_sast/perfil.json`. Só utiliza cópia cujas regras também tenham os hashes esperados. Candidato atual divergente é registrado como aviso/fonte observada, sem aceitação silenciosa. Nenhum scan é executado.

### Formatos opcionais implementados

Política de pesos JSON: `schema_versao="1.0"`, `versao` textual, `pesos` como mapa severidade→número finito positivo e `aliases` opcional como mapa alias→severidade declarada. Sem peso para algum valor presente, a métrica ponderada é indisponível. A política é registrada por hash.

Evidência RRIS JSON: `schema_versao`, `execucao`, `commit_baseline`, `hashes_catalogo`, `perfil_sha256`, `definicao_f`, `patches`, `ordem_aplicacao`, `conflitos`, `nao_aplicadas`, `perfil`, `scan_antes`, `scan_depois`, `validacao_funcional`. Referências de arquivos são objetos `{arquivo, sha256}` relativos à pasta do manifesto; itens de `patches` incluem `tentativa_id`. `ordem_aplicacao` lista os IDs na ordem dos patches efetivamente aplicados; `nao_aplicadas` lista IDs excluídos; conflitos identificam `tentativa_id` presente nessa lista.

Scans seguem a estrutura JSON do Semgrep, com `version`, `results` e `errors`, caminhos relativos normalizados e `falha_operacional` opcional. O perfil e suas regras são copiados para a evidência e verificados. O artefato funcional inclui `passou` booleano. A lista de arquivos alterados vem das tentativas aceitas, não de uma estimativa por contagem de findings. Diagnóstico anterior desaparecido sem evidência de cobertura também impede comparação conclusiva.

Publicação exclusiva no ambiente Linux usa `renameat2(RENAME_NOREPLACE)`, protegendo inclusive contra destino vazio criado no instante da promoção. Windows utiliza rename sem substituição; plataformas sem mecanismo exclusivo suportado recusam a publicação.
