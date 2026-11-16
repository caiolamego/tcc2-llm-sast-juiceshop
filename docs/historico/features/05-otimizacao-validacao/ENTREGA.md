# Entrega da feature 05 — otimização da validação

**Data:** 16/10/2026. **Status:** implementada e validada, com limitações registradas.

A implementação oferece as duas políticas de validação, mapa explícito dos 46
arquivos, caches separados de SAST/validação funcional, triagem, repetição seletiva
experimental, contrato 3.0 e replay sem LLM. As opções são propagadas pelo lançador,
painel, tentativa individual e sondagem. Os leitores continuam aceitando 1.0/2.0,
sem modificar contratos ou tentativas anteriores.

Os padrões continuam `historica_v1`, K=1, cache desligado e repetição ampla.
O `.env`, os limites e `config/execucao.yaml` foram preservados. Não houve novas
chamadas à LLM, commit, push ou campanha de correção dos 78 casos.

## Resultado medido

A comparação usa **96 replays: 12 rodadas dos mesmos oito patches arquivados**.
Referência e otimizado K=1 foram alternados: referência/otimizado na primeira
repetição, otimizado/referência na segunda e referência/otimizado na terceira.
As três repetições de K=2 foram feitas depois da preparação completa de `wt-2`.

| Cenário | Repetições | Mediana do tempo de execução | Intervalo observado |
|---|---:|---:|---:|
| Histórica K=1, sem cache | 3 | 1.354,655 s (22min35s) | 1.353,070–1.364,499 s |
| Otimizada K=1, cache frio | 3 | 1.348,652 s (22min29s) | 1.344,491–1.356,852 s |
| Otimizada K=2, cache frio | 3 | 1.133,274 s (18min53s) | 1.130,759–1.206,575 s |
| Otimizada K=1, cache quente | 1 | 1.068,796 s | uma observação |
| Otimizada K=2, cache quente | 1 | 1.104,275 s | uma observação |
| Otimizada K=1, repetição seletiva, sem cache | 1 | 1.187,975 s | uma observação |

O ganho mediano do otimizado K=1 sobre a referência foi **0,443%**, pequeno diante
da variação observada. K=2 reduziu o tempo mediano em **15,970%** comparado ao
mesmo otimizado K=1 com cache frio. Isso mede duração total, não aceleração de
cada tentativa. A preparação é contabilizada separadamente: cerca de 74–81 s
por rodada K=1 e 93–100 s por rodada K=2, além da instalação inicial.

As observações únicas de cache quente/seletiva são exploratórias; não demonstram
um ganho reproduzível de três repetições. Em particular, K=2 com cache quente
foi mais lento que K=1 com cache quente nesta observação.

Evidências: [resumo](../../../../outputs/feature05/COMPARACAO_V2/RESUMO.md),
[JSON com tempos, diferenças e recursos](../../../../outputs/feature05/COMPARACAO_V2/comparacao.json),
[CSV](../../../../outputs/feature05/COMPARACAO_V2/tempos.csv) e
[manifesto de hashes das entradas](../../../../outputs/feature05/COMPARACAO_V2/manifesto.json).
A consolidação foi repetida em destino novo e seus quatro arquivos são idênticos
byte a byte.

## Concordância e limites

R, M e as três definições de F coincidiram nos 96 replays válidos. KeyServer
preservou R/M indeterminados por ambiguidade SAST e F positivo. Login preservou
R=M=1, `F_criterio=1` e `F_marcador=F_sem_separacao=0`, com cinco testes de ataques
SQL persistentes pertencentes a D pela definição de critério.

Houve **uma diferença nas listas de falhas intermitentes**: o teste externo do
PasteBin em `internet-resources.test.ts`, no P4 de keyServer, cenário
`OPT_QUENTE_K2_V3`. Ela não mudou R/M/F, mas impede declarar igualdade completa
das falhas em todos os cenários. O JSON comparativo preserva essa diferença.

No cenário seletivo ocorreram repetições nos quatro patches de login. O JUnit
confirmou os testes esperados e as falhas persistentes coincidiram com a repetição
ampla. Isso cobre esse conjunto; não demonstra equivalência para todos os testes,
hooks ou dependências de ordem. A opção segue desligada por padrão.

O cache frio reutilizou três scans por rodada otimizada; o quente reutilizou os
oito. **Não houve hit funcional nos 96 replays válidos.** A identidade do estado
ou ambiente mudou após a validação e o guard recusou publicar essas evidências.
Não se removeu essa proteção para obter ganho. O reuso funcional é exercitado com
fixtures estáveis nos testes; seu benefício real não foi demonstrado neste alvo.
Uma comparação SAST indeterminada não impediu reutilizar um scan operacionalmente
válido; R/M foram recalculados para cada ocorrência.

Os picos amostrados da soma de RSS dos descendentes ficaram aproximadamente em
5,1–5,4 GiB para K=1 e 5,9–6,3 GiB para K=2 nas rodadas frias. Páginas compartilhadas
podem ser contadas mais de uma vez; isso não representa consumo físico exclusivo.
O ambiente de desktop e serviços externos introduzem variação. Oito patches de
duas issues não representam todas as alterações possíveis nos 78 casos.

## Preparação e rastreabilidade

Alvo: `f915bddd82790d0f3018902d36ae9b4241a5f51f`. Ambiente: Python 3.12.3,
Node v24.14.0, npm 11.9.0 e Semgrep 1.177.0. O catálogo, perfil do piloto e baseline
funcional anteriores foram usados sem regeneração.

`wt-2` foi criada pelo Git existente. Copiaram-se os lockfiles locais e os assets
`frontend/dist` já usados em `wt-1`. A instalação usou
`npm ci --ignore-scripts --no-audit --no-fund` e
`npm rebuild sqlite3 --ignore-scripts=false`; depois executou-se
`npm run build:server`. Não houve novo build Angular nem instalação/execução de
Cypress. Os 25 testes de `file-serving` passaram após completar a preparação. O `npm ci` reportou 14 s; rebuild SQLite e build inicial não tiveram cronômetros individuais e seus logs estão preservados, separados dos tempos de preparação por rodada.

A primeira preparação deixou `build/server.js` ausente em `wt-2`. Isso provocou
falhas de precondição nas primeiras medições K=2. `R1_OPT_FRIO_K2_V2` e
`R2_OPT_FRIO_K2_V2` foram preservadas como diagnóstico e **excluídas** da comparação;
a segunda foi interrompida com restauração segura. Os quatro cenários K=2 foram
refeitos em diretórios/cache V3 novos, sem sobrescrever V2. Os smoke tests iniciais
e `R1_REF_K1` também são preliminares, fora da população comparativa.

O snapshot medido está em [PREPARACAO_V2](../../../../outputs/feature05/PREPARACAO_V2/ambiente.json).
Após a matriz, adicionaram-se duas proteções: recusa de cache para JUnit com falha
de carregamento de arquivo/precondição e recusa antecipada do benchmark quando
faltam builds. A decisão de elegibilidade antes/depois foi conferida nas 96
validações válidas e não mudou. Os tempos acima pertencem ao snapshot medido;
o smoke final valida o código com essas proteções, sem entrar nas estatísticas.
As identidades novas invalidam caches/retomadas do snapshot anterior. O [snapshot final](../../../../outputs/feature05/VERIFICACAO_FINAL/fontes_sha256.json) e o [smoke](../../../../outputs/feature05/SMOKE_FINAL_K2/manifesto.json) preservam essa distinção.

## Integração e verificações

- [x] 203 testes unitários passaram; referência inicial: 169.
- [x] 28/28 testes das regras Semgrep passaram.
- [x] Contrato 3.0, preflight de duas issues com oito prompts e dry-run de duas
  tentativas P1, sem cliente LLM real; relatórios de métricas gerados.
- [x] Mensagens e hashes dos oito prompts comparados ao preflight original: iguais.
- [x] Comparação determinística e decisões de cache conferidas nos 96 replays.
- [x] 1.025 arquivos históricos tiveram SHA-256 preservado.
- [x] Smoke final K=2 com as proteções adicionais: R/M e três F compatíveis, worktrees restauradas; sintaxe JS, links locais e `git diff --check` aprovados.

Saídas de integração: [preflight final](../../../../outputs/feature05/AMP_PREFLIGHT_FINAL/preflight.json),
[métricas dry-run](../../../../outputs/feature05/AMP_DRY_METRICAS_V2/metricas.json) e
[métricas preflight finais](../../../../outputs/feature05/AMP_PREFLIGHT_FINAL_METRICAS/metricas.json).
Preflight não é tentativa de remediação. Os replays não entram na população de
novas gerações e não são réplicas independentes de LLM. O orçamento permaneceu
com oito chamadas históricas e US$ 0,010012 acumulados, sem cobrança nova.

Hashes históricos e logs de testes/preparação estão em
[VERIFICACAO_FINAL](../../../../outputs/feature05/VERIFICACAO_FINAL/verificacoes.json).

## Reproduzir e continuar

Use um destino/cache novo para repetir a medição fria; preserve a mesma identidade
entre as duas execuções para medir cache quente. O script nunca instala dependências
ou cria worktrees automaticamente.

```bash
.venv/bin/python scripts/experiment/benchmark_validation.py \
  --origem outputs/piloto_2_issues/AMP_PILOTO_2_REAL_20261014 \
  --saida outputs/feature05/REPLAY_NOVO \
  --politica-validacao otimizada_v1 \
  --mapa-testes config/mapa_testes_relacionados.yaml \
  --cache-validacao leitura-escrita --cache-dir .cache/replay_novo \
  --repeticao-api ampla --k 2

make test-unit PYTHON=.venv/bin/python
make test-rules SEMGREP=.venv/bin/semgrep
python executar.py --config config/execucao_otimizada.exemplo.yaml --mostrar-comando
```

Recomendação: manter os padrões atuais e, para o próximo piloto controlado,
avaliar `otimizada_v1`, K=2, cache de leitura/escrita e repetição ampla. Congelar a
política antes da campanha e mapear mais funcionalidades: hoje apenas login e
keyServer têm associações específicas; os outros 44 arquivos usam fallback amplo.
Investigar a mudança de identidade funcional antes de esperar ganho desse cache.
A repetição seletiva continua experimental. Nenhuma configuração de execução real
foi ativada automaticamente.
