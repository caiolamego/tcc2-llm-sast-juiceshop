# Resultados (`outputs/`)

Tudo o que o projeto já produziu: resultados oficiais, pilotos, testes de desenvolvimento e o histórico.
**Nada aqui é movido nem editado.** O código, as configurações, a referência Docker e os próprios
registros apontam para estes caminhos, e cada resultado precisa continuar ligado ao comando e ao código
que o geraram. Este índice diz o papel de cada pasta.

## Onde está o resultado oficial

Campanha dos 52 casos preparados, P1–P4, gpt-4.1-mini, no ambiente Docker oficial (19/10/2026):

- registros: `campanha_docker/AMP_PAINEL_20261019T183425Z_282e13b4/`
- métricas: `campanha_docker/AMP_PAINEL_20261019T183425Z_282e13b4_METRICAS/`
- baseline funcional usado: `baselines/docker/oficial_v1/` (imagem de `docker/historico/referencia_oficial_v1.json`)

A referência oficial atual, para execuções novas, é `baselines/docker/oficial_v2/`, gerada em 26/10/2026 depois da
reorganização do código (`docker/referencia.json`). Os 39 grupos de testes deram o mesmo resultado nas duas.

## Pastas por papel

### Oficial

| Pasta | Conteúdo |
|---|---|
| `campanha_docker/` | `AMP_PAINEL_20261019T183425Z_282e13b4`: campanha oficial (191 tentativas em duas sessões; a segunda completou um caso interrompido por falha de conexão). `AMP_PREFLIGHT_20261019T174514Z_fe15bc52`: preflight dos 52 casos (208 prompts). `AMP_PAINEL_20261019T175741Z_d61671f5`: preflight pelo painel, sem tentativas. `AMP_PAINEL_20261019T181245Z_1aca0df2`: execução interrompida com 13 tentativas, que revelou o problema de recuo na aplicação dos patches. |
| `baselines/docker/oficial_v2/` | Baseline funcional oficial atual (26/10/2026), ligado à imagem de `docker/referencia.json`. |
| `baselines/docker/oficial_v1/` | Baseline usado pela campanha de 19/10, ligado à imagem de `docker/historico/referencia_oficial_v1.json`. |

### Entradas geradas

| Pasta | Conteúdo |
|---|---|
| `catalogos/ampliado_v1/` | Catálogo dos 78 casos por ocorrência. |
| `cobertura_funcional/COBERTURA_V1/` | Auditoria da cobertura funcional (52 preparados, 26 bloqueados). |
| `sast_antes/` | Scan e catálogo do modo histórico (JS001–JS012), usados por E01–E03. |

### Pilotos e revalidações

| Pasta | Conteúdo |
|---|---|
| `execucoes/` | Execuções de 17/10 pelo painel, fora do Docker. `AMP_PAINEL_20261017T064627Z_bf4efba0` é o piloto de 10 casos (40 tentativas). |
| `piloto_2_issues/` | Piloto de 2 casos (14/10). |
| `piloto_colab_1_issue/` | Teste do Qwen no Colab. |
| `revalidacoes/` | `PILOTO10_CORRECAO_V1`: replay sem LLM do piloto de 10 casos. `DOCKER_V1`: baseline com o problema do `safetyMode` (não usar). `DOCKER_V2`: baseline corrigido de uma imagem local. `ANCORAS_INDENTACAO_V1`: replay das âncoras com recuo. `REORGANIZACAO_20261026`: verificação de que a reorganização do repositório não mudou o funcionamento (comparação antes × depois e as ferramentas usadas); `fase2_codigo/` cobre a reorganização do código e a referência v2. |
| `diagnosticos_llm/` | Diagnósticos do Qwen no Colab. |
| `painel/` | Logs e estado das execuções iniciadas pelo painel. |

### Desenvolvimento

| Pasta | Conteúdo |
|---|---|
| `feature02/` … `feature07/` | Evidências do desenvolvimento de cada feature: dry-runs, preflights, testes e verificações. As descrições estão em `docs/historico/features/`. |

### Auditoria exploratória das regras

| Pasta | Conteúdo |
|---|---|
| `auditoria_sast/` | Scans exploratórios, matriz de desafios, candidatos de correção, avaliação dos codefixes e comparações v1/v2. |

### Histórico E01–E03 (formato do TCC 1)

Formato "plano" do §3.10 do TCC 1: uma pasta por tipo de artefato, na raiz de `outputs/`.

| Pasta | Conteúdo |
|---|---|
| `patches/`, `respostas_llm/`, `tentativas/` | Artefatos das tentativas JS001–JS012. |
| `resultados_consolidados/` | Registros e métricas de E01 e E02. |
| `sondagens/`, `validacao_cenarios/`, `custos_validacao/` | Experimentos das fases F2–F5. |
| `baseline_testes.json` | Linha de base de testes do modo histórico (caminho fixo no código). |

## Estrutura de uma execução

```
<EXECUCAO>/
  contrato_execucao.json        configuração e hashes que a execução promete respeitar
  sast_antes/                   SAST inicial e reprodução do catálogo
  prompts/                      prompt de cada tentativa
  respostas_llm/                resposta da LLM
  patches/                      diff aplicado
  codigos_corrigidos/           arquivo corrigido
  sast_depois/                  SAST depois da correção
  comparacoes/                  comparação antes/depois (R e M)
  testes/                       resultado dos testes (F)
  cobertura_funcional/          revisão e baseline usados
  resultados_consolidados/      execucoes.jsonl (uma linha por tentativa) e sessões
<EXECUCAO>_METRICAS/            métricas consolidadas (JSON e CSV)
```

## Nome dos arquivos

Cada artefato usa o identificador da tentativa, no padrão da Figura 3 do TCC 1:

```
AMP3aec6cd362844193 _ A07 _ HARDCRED _ P3 _ AMP_PAINEL_20261019T183425Z_282e13b4
caso (hash estável)   OWASP  vulnerab.  prompt  execução (modo + data UTC + sufixo)
```

Quando o alerta não tem categoria OWASP, o segundo campo é `SEMOWASP`. O tipo de artefato é dado pela
pasta (`prompts/`, `patches/`, ...).
