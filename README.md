# Correção de vulnerabilidades em código com LLMs

Guia de continuidade: [diagnóstico, checklists e plano do TCC2](docs/GUIA_CONTINUIDADE_TCC2.md).

Para iniciar com as configurações do piloto, na raiz deste repositório:

```bash
python executar.py
```

Essa entrada usa automaticamente a `.venv` existente e executa **a LLM real** para
`routes/login.ts` e `routes/keyServer.ts`, com P1–P4, K=1 e consolidação de métricas
ao final. Casos, estratégias e caminhos ficam em [config/execucao.yaml](config/execucao.yaml).
A chave e os limites continuam no `.env`; o orçamento é acumulado entre execuções,
conforme `.cache/orcamento_llm.json`. O lançador não aumenta limites nem apaga esse histórico.

Cada chamada cria uma execução nova em `outputs/execucoes/` e uma pasta irmã com
sufixo `_METRICAS`. Se o pipeline falhar, o lançador preserva os artefatos e retorna
o código da falha, sem iniciar a consolidação. A retomada de uma execução existente
continua disponível pela interface completa abaixo.

```bash
python executar.py --modo preflight   # prepara prompts sem chamar a LLM
python executar.py --modo dry-run     # valida com respostas simuladas
python executar.py --mostrar-comando # apenas mostra os comandos delegados
```

O ambiente e o worktree devem estar previamente preparados. O lançador reutiliza
os gates, contratos e validações do pipeline; não instala dependências nem modifica
os resultados anteriores. Também funciona por caminho absoluto, a partir de outra pasta.

Para controlar e acompanhar pelo navegador:

```bash
python painel.py
```

Abra **http://127.0.0.1:8765**. O painel oferece início, parada após a tentativa atual,
log ao vivo, cronômetro da sessão e tempos por issue/prompt (LLM, SAST, validação e
total). O seletor de histórico permite consultar as tentativas já registradas,
incluindo o piloto de duas issues. Abrir o painel não inicia o pipeline.
Veja [uso e limites do painel](docs/painel_local.md).

A configuração de entrada usa `relacionada_v1`: somente os testes mapeados para
a funcionalidade alterada, além de compilação e SAST global. Veja
[como funciona](docs/validacao_relacionada.md). A política `otimizada_v1` da feature
05 permanece como alternativa com confirmação ampla. Para
conferir seus comandos sem executar o pipeline:

```bash
python executar.py --config config/execucao_otimizada.exemplo.yaml --mostrar-comando
```

O exemplo usa preflight, K=1, cache de validação e repetição ampla de API. A
[feature 05](features/05-otimizacao-validacao/README.md) descreve a seleção explícita,
o reuso de evidências e o [benchmark sem LLM](features/05-otimizacao-validacao/VALIDACAO.md).

Pipeline automatizado que integra análise estática de segurança (SAST), Modelos de Linguagem de Grande Escala (LLMs), estratégias de contextualização e testes automatizados para gerar e **validar** correções de vulnerabilidades no OWASP Juice Shop.

Trabalho de Conclusão de Curso 2 — Engenharia de Software, Faculdade de Ciências e Tecnologias em Engenharia (FCTE), Universidade de Brasília.

**Autores:** Matheus de Siqueira Brant e Caio Magalhães Lamego
**Orientadora:** Profa. Dra. Elaine Venson

---

## Sobre

LLMs geram correções de código com facilidade, mas uma correção que apenas faz o alerta do SAST desaparecer não é necessariamente uma correção. Ela pode remover o sintoma sem tratar a causa, ou eliminar a vulnerabilidade quebrando o funcionamento da aplicação.

Este projeto avalia se um pipeline automatizado consegue corrigir vulnerabilidades **reais**, detectadas por análise estática em um projeto open source de porte, sob critérios de validação mais rigorosos que a simples ausência do alerta.

Uma correção só é considerada válida quando satisfaz **simultaneamente** três critérios:

| Variável | Critério |
|:---:|---|
| `R` | A vulnerabilidade original deixou de ser detectada na reanálise estática |
| `F` | Os testes funcionais continuam passando |
| `M` | Nenhuma nova issue de segurança foi introduzida |

Para as correções aceitas, aplica-se ainda uma verificação dinâmica complementar (`D`): se o desafio de segurança correspondente do próprio Juice Shop deixa de ser resolvível, a vulnerabilidade foi efetivamente removida — e não apenas o alerta.

### Pergunta de pesquisa

Em que medida a integração entre ferramentas SAST, LLMs e estratégias de contextualização apoia a correção de vulnerabilidades em código-fonte sem comprometer a funcionalidade da aplicação?

### Estratégias de prompt comparadas

Cada vulnerabilidade é submetida às estratégias em sequência, da mais simples à mais completa, interrompendo na primeira correção validada.

| | Estratégia | Composição do prompt |
|---|---|---|
| `P1` | Simples | Código vulnerável + instrução direta |
| `P2` | Raciocínio guiado | `P1` + roteiro de análise em etapas |
| `P3` | RAG | Código + diagnóstico SAST + contexto recuperado |
| `P4` | RAG + raciocínio guiado | `P3` + roteiro de análise em etapas |

---

## Arquitetura

```
                       ┌──────────────────────────┐
                       │  OWASP Juice Shop        │
                       │  (commit fixado)         │
                       └────────────┬─────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  SAST baseline        │  Semgrep
                        │  + filtragem          │
                        └───────────┬───────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  Catálogo de issues   │  CWE, OWASP, causa raiz
                        └───────────┬───────────┘
                                    │
          ┌─────────────────────────▼─────────────────────────┐
          │  Por vulnerabilidade (paralelo, worktrees)        │
          │                                                   │
          │   P1 → P2 → P3 → P4   (para na primeira válida)   │
          │    │                                              │
          │    ├─ recuperação de fragmentos (RAG)             │
          │    ├─ montagem do prompt                          │
          │    ├─ chamada à LLM (saída estruturada)           │
          │    ├─ aplicação do patch por âncora               │
          │    ├─ reanálise SAST            ──────────► R     │
          │    ├─ validação em camadas      ──────────► F     │
          │    └─ diferença de findings     ──────────► M     │
          └─────────────────────────┬─────────────────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  Confirmação dinâmica │  ─────────► D
                        │  (desafios Cypress)   │
                        └───────────┬───────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  Métricas e artefatos │
                        └───────────────────────┘
```

### Validação em camadas

Para viabilizar a execução em escala, a validação funcional é organizada em camadas de custo crescente com interrupção antecipada. Uma correção reprovada em qualquer camada é reprovada no critério `F`.

| Tier | Verificação | Ferramenta |
|:---:|---|---|
| T0 | Compilação | `tsc --noEmit` |
| T1 | Lint (não bloqueante) | ESLint |
| T2 | Testes unitários do arquivo alterado | Node.js test runner + tsx |
| T3 | Suíte unitária de servidor | Node.js test runner + tsx |
| T4 | Testes de API | Node.js test runner + supertest |
| T5 | Desafios de segurança (conjunto `D`) | Cypress |

Os testes que verificam comportamento de negócio (conjunto `F`) e os que resolvem desafios de segurança (conjunto `D`) são particionados e têm papéis distintos: como o Juice Shop é deliberadamente vulnerável, a reprovação de um teste de desafio após a correção é **evidência de sucesso**, não de falha funcional.

---

## Métricas

| Sigla | Métrica | Definição |
|---|---|---|
| **TRV** | Taxa de Remediação Validada | Σ(R·F·M) / m |
| **TRV-P** | TRV ponderada por severidade | Σ(w·R·F·M) / Σw |
| **CR** | Cobertura de Remediação | vulnerabilidades corrigidas / submetidas |
| **TRI** | Taxa de Remoção de Issues | Σ R / m |
| **TPF** | Taxa de Preservação Funcional | Σ F / m |
| **TNINI** | Taxa de Não Introdução de Novas Issues | Σ M / m |
| **TFF** | Taxa de Falha Funcional | 1 − TPF |
| **TAP** | Taxa de Aplicabilidade do Patch | patches aplicáveis / m |
| **RRIS** | Redução Relativa de Issues de Segurança | (I_antes − I_depois) / I_antes |

O comando histórico mantém seus JSONs e cálculos. A feature 04 acrescenta consolidação verificável em JSON/CSV, por estratégia, caso, CWE/OWASP, severidade, regra, auditoria e RAG. RRIS exige evidência conjunta externa; TRV-P exige política explícita de pesos. Sem essas entradas, as métricas opcionais ficam nulas com motivo registrado.

---

## Pré-requisitos

| Requisito | Versão |
|---|---|
| Python | 3.11+ |
| Node.js | conforme `engines` do Juice Shop (ver `.nvmrc`) |
| Git | 2.35+ (suporte a `worktree`) |
| Semgrep | 1.80+ |
| Chave de API | OpenAI |

Espaço em disco: ~6 GB (pool de 4 worktrees com dependências instaladas).

---

## Instalação

```bash
git clone https://github.com/<org>/tcc2-llm-sast-juiceshop.git
cd tcc2-llm-sast-juiceshop

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # preencha OPENAI_API_KEY e JUICESHOP_COMMIT

./scripts/setup/setup_target.sh 4 # clona o alvo e prepara 4 worktrees (demora)
```

---

## Uso

Execute os comandos a partir da raiz, com as dependências Python instaladas e o alvo preparado. A auditoria exploratória e o catálogo histórico são conjuntos separados.

```bash
# Auditoria: novos scans e classificação (escolha uma saída nova).
python scripts/audit/scan_semgrep_exploratorio.py --help
python scripts/audit/classify_combined_scan.py --help

# Catálogo a partir do baseline arquivado e referência de testes.
python scripts/experiment/build_issue_catalog.py --help
python scripts/experiment/baseline_testes.py --help

# Correções reais: P1/P2/P3/P4 disponíveis; requerem ambiente e orçamento configurados.
PYTHONPATH=src python -m pipeline.run_pipeline --execucao E03 --estrategias P1,P2

# Métricas das execuções já registradas; não chama a API.
python scripts/reports/metricas_execucao.py E02

# Testes do projeto; não executam experimentos nem chamadas à LLM.
make test-unit
make test-rules
```

A execução das correções pode ser retomada pelo identificador da execução. Use os comandos nas subpastas; as entradas antigas na raiz de `scripts/` foram removidas. Não existe ainda um comando de oráculo Cypress final ou de consolidação completa em CSV.

## Estrutura

A base documental está em `knowledge_base/`; o recuperador está em `src/pipeline/rag/`, e sua validação editorial em `scripts/experiment/validate_knowledge_base.py`.

```text
config/               configurações, critérios e mapeamentos
executar.py           entrada curta pelo terminal
painel.py             entrada do painel local
frontend/painel/      interface HTML/CSS/JS do painel
knowledge_base/       dez documentos, índice e manifesto RAG 1.0
rules/rodada1..12/    regras locais e fixtures do Semgrep
scripts/setup/        preparação do alvo
scripts/audit/        scans, triagem, matrizes e verificações das rodadas
scripts/experiment/   catálogo, baselines e tentativas de correção
scripts/reports/      relatórios e métricas
src/pipeline/         componentes reutilizáveis e orquestrador
tests/unit/           testes Python do projeto
tests/integration/    testes dinâmicos e inventário padronizado das rodadas
docs/auditoria/       relatórios das rodadas e seleção exploratória
outputs/              evidências históricas e resultados
workspace/            alvo e worktrees locais (não versionados)
```

Veja [estrutura do projeto](docs/estrutura_projeto.md) para os comandos, limites e preservação dos resultados. Os testes `.mjs` estão em `tests/integration/rodadaN/`; as fontes originais estão em `tests/integration/historico/` para conferir hashes antigos. Veja [validação das rodadas](tests/integration/README.md).

### Rastreabilidade dos artefatos

Cada tentativa recebe um identificador único que nomeia todos os seus artefatos, dispensando banco de dados — o nome do arquivo é a chave estrangeira.

```
<CASO>_<OWASP>_<VULN>_<PROMPT>_<EXECUCAO>_<ARTEFATO>.<ext>

JS007_A05_SQLI_P3_E01_prompt.txt
JS007_A05_SQLI_P3_E01_resposta.json
JS007_A05_SQLI_P3_E01_sast_depois.json
```

Os registros por tentativa estão em `outputs/resultados_consolidados/execucoes.jsonl`; a organização é descrita em [estrutura do projeto](docs/estrutura_projeto.md).

---

## Reprodutibilidade

Toda execução registra o commit do alvo, a versão do Semgrep e dos rulesets, o modelo, a semente e o `system_fingerprint` de cada chamada. As chamadas usam temperatura zero e semente fixa.

O comportamento de LLMs permanece não determinístico mesmo sob esses controles, e os rulesets do registro do Semgrep não são versionados — por isso os JSONs brutos de cada análise são arquivados como fonte primária. As limitações estão detalhadas na monografia.

---

## Aviso

O OWASP Juice Shop é uma aplicação **deliberadamente vulnerável**, usada aqui como objeto de estudo. Nunca a exponha em rede pública ou em ambiente compartilhado. Todo o experimento roda localmente, em cópias isoladas.

Este repositório não contém, nem deve conter, chaves de API. Se uma chave for exposta acidentalmente, revogue-a imediatamente no painel do provedor.

---

## Status

Uma auditoria exploratoria de cobertura do Semgrep, com scans adicionais e
uma regra de diagnostico para Angular, esta em
[`docs/auditoria/auditoria_cobertura_semgrep.md`](docs/auditoria/auditoria_cobertura_semgrep.md).
Esses resultados ainda nao substituem o baseline oficial de 12 casos.

A matriz exploratoria de desafios, alertas e triagem fica em
[`outputs/auditoria_sast/matriz_desafios.csv`](outputs/auditoria_sast/matriz_desafios.csv)
(versao completa em JSON). Ela preserva os 113 desafios no catalogo e distingue
alertas confirmados, falsos positivos e inconclusivos; nao altera os casos JS001-JS012.

A proposta de segunda coorte agrupa 20 desafios confirmados em 16 causas de
correcao, com quatro pilotos ainda dependentes de testes de seguranca e de
congelamento das regras. Ver
[`docs/auditoria/selecao_exploratoria_correcao.md`](docs/auditoria/selecao_exploratoria_correcao.md)
e [`outputs/auditoria_sast/candidatos_correcao.csv`](outputs/auditoria_sast/candidatos_correcao.csv).

A segunda rodada exploratoria acrescentou dois desafios com alerta confirmado
(senha fraca e metricas expostas): 44 alertas brutos no perfil ampliado,
22 desafios distintos confirmados. A triagem, os dois desafios investigados
sem nova regra e os comandos de reproducao estao em
[`docs/auditoria/auditoria_rodada2.md`](docs/auditoria/auditoria_rodada2.md). Nenhum resultado da
LLM foi produzido nesta rodada.

A terceira rodada delimitada identificou mais um desafio com alerta confirmado,
`resetPasswordMortyChallenge`, chegando a 45 alertas exploratorios brutos e
23 desafios distintos confirmados. Os dez desafios marcados que permanecem
sem alerta confiavel e as limitacoes de deployment estao em
[`docs/auditoria/auditoria_rodada3.md`](docs/auditoria/auditoria_rodada3.md). Isso ainda nao
substitui o baseline do experimento principal.

Uma quarta rodada expandiu a busca para desafios sem marcador e confirmou
mais cinco, chegando a 51 alertas exploratorios brutos e 28 desafios
distintos. A triagem (inclusive um falso positivo), os quatro padroes de regra
e as limitacoes estao em
[`docs/auditoria/auditoria_rodada4.md`](docs/auditoria/auditoria_rodada4.md).

A quinta rodada chegou a **56 alertas exploratorios brutos e 31 desafios
distintos confirmados por revisao estatica**: 38 alertas confirmados, 16 falsos
positivos e 2 inconclusivos. Foram acrescentados acesso a outra cesta e dois
desafios B2B que compartilham o mesmo ponto de correcao. Detalhes e limites em
[`docs/auditoria/auditoria_rodada5.md`](docs/auditoria/auditoria_rodada5.md); matriz dessa rodada em
[`outputs/auditoria_sast/rodada5/matriz_desafios.csv`](outputs/auditoria_sast/rodada5/matriz_desafios.csv).
O baseline e a selecao antiga de candidatos para a LLM nao foram alterados.

A sexta rodada chegou a **59 alertas exploratorios brutos e 35 desafios
distintos confirmados por revisao estatica**: 41 alertas confirmados, 16 falsos
positivos e 2 inconclusivos. Sao tres alertas novos (cesta, senha atual e
CAPTCHA) e uma associacao adicional de SSTI a alertas existentes, sem inflar
a contagem bruta. A [matriz dessa rodada](outputs/auditoria_sast/rodada6/matriz_desafios.csv)
e o [relatorio da rodada 6](docs/auditoria/auditoria_rodada6.md) registram evidencias,
revisoes, o scan completo com timeout de 30 segundos e proximos candidatos.
Baseline e snapshots anteriores permanecem intactos; nenhuma LLM foi executada.

A setima rodada chegou a **64 alertas exploratorios brutos e 37 desafios
distintos confirmados**: 43 alertas confirmados, 19 falsos positivos e 2
inconclusivos. Acrescentou autoria de avaliacoes e promocao Deluxe sem validar
modo de pagamento, com revisao dos fluxos e testes isolados das rotas reais
usando dependencias simuladas. A [matriz atual](outputs/auditoria_sast/rodada7/matriz_desafios.csv)
e o [relatorio da rodada 7](docs/auditoria/auditoria_rodada7.md) incluem os tres falsos
positivos novos e os limites dos testes. Nenhum baseline ou candidato antigo
de correcao foi alterado; nenhuma LLM foi executada.

A oitava rodada incluiu os quatro candidatos priorizados: exportacao de dados,
quantidade negativa, cadastro administrativo e autoria de feedback. O perfil
acumulado chegou a **68 alertas brutos e 41 desafios distintos confirmados**:
47 alertas confirmados, 19 falsos positivos e 2 inconclusivos. A
[matriz da rodada 8](outputs/auditoria_sast/rodada8/matriz_desafios.csv) e o
[relatorio](docs/auditoria/auditoria_rodada8.md) distinguem testes HTTP com API gerada e
SQLite reais dos testes com dependencias simuladas. A expansao para aqui,
conforme o pedido de quatro candidatos; baseline, selecao antiga de correcao
e resultados anteriores permanecem intactos. Nenhuma LLM foi executada.

A nona rodada confirmou leitura local via `layout` e alteracao anonima de
produtos: **72 alertas brutos e 43 desafios distintos confirmados**, com
49 alertas confirmados, 21 falsos positivos e 2 inconclusivos. A
[matriz da rodada 9](outputs/auditoria_sast/rodada9/matriz_desafios.csv) usa
o scan completo, nao a primeira tentativa com timeout. O
[relatorio](docs/auditoria/auditoria_rodada9.md) documenta integracao local com hbs e
API gerada reais, controles, falsos positivos e limites. Nenhuma LLM foi
executada; o baseline e a selecao antiga para correcao permanecem intactos.

A decima rodada confirmou falsificacao de cupons e validade baseada em data
do cliente: **74 alertas brutos e 45 desafios distintos confirmados**, sendo
51 alertas confirmados, 21 falsos positivos e 2 inconclusivos. A
[matriz da rodada 10](outputs/auditoria_sast/rodada10/matriz_desafios.csv) e o
[relatorio](docs/auditoria/auditoria_rodada10.md) registram testes isolados do codigo real
e scans repetidos. Oito dos dez prioritarios foram incluidos, encerrando a
expansao pela meta de cobertura. A consolidacao da selecao versionada de
causas para correcao ainda esta pendente; nenhuma LLM foi executada.

A rodada 11, solicitada como expansao adicional, chegou a **76 alertas brutos
e 47 desafios distintos confirmados** (53 alertas confirmados, 21 falsos
positivos, 2 inconclusivos). Confirmou concorrencia em curtidas com MarsDB
real e JSONP **condicionado a origem atacante no mesmo site**: o controle
cross-site com cookie Lax nao vazou email. A
[matriz](outputs/auditoria_sast/rodada11/matriz_desafios.csv) e o
[relatorio](docs/auditoria/auditoria_rodada11.md) registram o teste de navegador,
precondicoes e limites; nao houve LLM ou alteracao do baseline.

A rodada 12 atingiu **50 desafios distintos confirmados**, com 78 alertas
brutos (55 confirmados, 21 falsos positivos e 2 inconclusivos). Acrescentou
cadastro vazio, confirmacao de senha divergente e avaliacao zero, demonstrados
por HTTP e persistencia no SQLite. Dois alertas cobrem esses tres desafios,
sem equivaler automaticamente a tres causas independentes. A
[matriz](outputs/auditoria_sast/rodada12/matriz_desafios.csv) e o
[relatorio](docs/auditoria/auditoria_rodada12.md) preservam condicoes e limitacoes
anteriores, incluindo JSONP same-site. Nenhuma LLM foi executada.

| Fase | Situação |
|---|:---:|
| Preparação do ambiente e do alvo | Scripts e evidências existentes; preparação local necessária |
| Baseline SAST e catálogo de issues | Catálogo histórico de 12 casos e ampliado de 78; seleção explícita |
| Workspace e validação em camadas | Implementados, T0/T2/T3/T4 |
| Camada LLM, prompts e RAG | P1/P2/P3/P4 e P1L implementados; base 1.0 e preflight de 312 prompts validados |
| Orquestração e métricas | Implementadas parcialmente; consolidação final pendente |
| Execução exploratória | Rodadas de auditoria e E01/E02 registradas |
| Execução completa | Piloto e correções reais sobre os 78 casos ainda pendentes |
| Análise e redação | Relatórios técnicos existentes; análise final pendente |

---

## Licença

MIT. Ver [LICENSE](LICENSE).

O OWASP Juice Shop é distribuído sob licença própria e não é redistribuído neste repositório — é obtido em tempo de configuração a partir do repositório oficial, em commit fixado.


## Execução com catálogo ampliado

A feature 02 adiciona seleção do catálogo e perfil local, preflight e contrato de retomada.
Use o ambiente completo preparado em `.venv` e um worktree no commit fixado.

```bash
PYTHONPATH=src .venv/bin/python -m pipeline.run_pipeline \
  --execucao AMP_PREFLIGHT_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --perfil-sast config/perfis/ampliado_v1/perfil.json \
  --saida outputs/feature02/AMP_PREFLIGHT_01 \
  --somente-preflight --estrategias P1,P2 --k 1 \
  --semgrep-bin .venv/bin/semgrep
```

O preflight não chama a API, não aplica patches e não exige `node_modules`.
Para dry-run, usar outra execução/saída, `--dry-run` e uma referência de testes compatível
em `--baseline-testes`. Indeterminações SAST são registradas e não aceitas automaticamente.
Os nomes antigos JS continuam disponíveis no modo histórico; AMP usa identidade por ocorrência.

Veja a [especificação da integração](features/02-integracao-catalogo/README.md).


## RAG e preflight das quatro estratégias

A feature 03 publicou dez documentos genéricos em português na [base 1.0](knowledge_base/README.md). P3/P4 recuperam pela primeira CWE mapeada, depois pela categoria do catálogo e por último pelo contexto genérico. A categoria recuperada é registrada separadamente da original; não confirma uma vulnerabilidade. P1/P2/P1L mantiveram suas mensagens e hashes.

```bash
.venv/bin/python scripts/experiment/validate_knowledge_base.py
make test-unit PYTHON=.venv/bin/python
PYTHONPATH=src .venv/bin/python -m pipeline.run_pipeline \
  --execucao AMP_RAG_PREFLIGHT_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --perfil-sast config/perfis/ampliado_v1/perfil.json \
  --saida outputs/feature03/AMP_RAG_PREFLIGHT_01 \
  --estrategias P1,P2,P3,P4 --somente-preflight --k 1 \
  --semgrep-bin .venv/bin/semgrep
```

Essa saída já contém 312 prompts, com 156 recuperações P3/P4. O comando pode conferir a retomada compatível; mudanças científicas exigem nova execução/saída. Nenhuma chamada à API, patch ou validação funcional ocorre no preflight. Os oito diagnósticos preexistentes de parsing estão preservados.

Na entrega da feature 03, os contratos passaram a usar versão 2.0 com hashes dos componentes textuais e política de contexto. RAG inclui os hashes do manifesto, índice e documentos. Contratos 1.0 sem RAG só podem ser retomados com evidências completas de mensagens/hashes equivalentes para todos os pares solicitados; seus artefatos e identidade são preservados. Não adicionar P3/P4 a saídas antigas.

Veja a [entrega da feature 03](features/03-rag-prompts/ENTREGA.md) e a [cobertura por caso](outputs/feature03/cobertura_rag.json). Piloto com correções reais e cobertura específica de frontend seguem pendentes.


## Consolidação offline de métricas

```bash
.venv/bin/python scripts/reports/consolidate_metrics.py \
  --execucao AMP_DRY_01 \
  --entrada outputs/feature02/AMP_DRY_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --saida outputs/feature04/AMP_DRY_01_METRICAS_NOVA \
  --definicao-f criterio
```

Escolha uma saída nova: o comando recusa sobrescrita. Ele lê contratos, registros e artefatos arquivados; não chama LLM, executa scans ou aplica patches. Produz 13 artefatos JSON/CSV com numeradores, denominadores, motivos de indisponibilidade e manifesto. Preflight gera somente contagem de preparação, com métricas de remediação nulas. Simulações e P1L ficam separados do desenho real.

No modo ampliado, TRI/TPF/TNINI usam valores medidos; as proporções mínimas sobre todas as tentativas também são exportadas. TRV mantém todas as tentativas da população. TFF acompanha o denominador de TPF. O módulo reutilizável está em `src/pipeline/metrics/`; o comando histórico permanece disponível.

A [entrega da feature 04](features/04-metricas-consolidacao/ENTREGA.md) registra testes, reprodução e a divergência preexistente das regras remotas. Um [snapshot exato](outputs/feature04/preparacao/perfil_sast/perfil.json) foi recuperado do Git e usado na validação; os arquivos atuais e históricos foram preservados. Para futuras execuções SAST, selecionar um perfil íntegro explicitamente.


## Otimização opcional da validação

A [feature 05](features/05-otimizacao-validacao/ENTREGA.md) acrescenta as políticas
`historica_v1` e `otimizada_v1`, mapa explícito de testes, cache de evidências e
repetição de API `ampla|seletiva-experimental`. As otimizações exigem catálogo
ampliado; a política otimizada exige `--mapa-testes`. Novas execuções ampliadas
usam contrato 3.0 e continuam lendo 1.0/2.0 sem migrá-los.

Os 96 replays dos oito patches do piloto preservaram R/M/F. O ganho mediano de
cache frio K=1 foi 0,4%; K=2 reduziu a mediana em aproximadamente 16% sobre o
mesmo otimizado K=1. Cache quente e repetição seletiva tiveram somente uma rodada;
o relatório registra uma intermitência externa e a ausência de hits funcionais.
Não são novas correções ou amostras independentes da LLM.

O CLI mantém a política histórica por compatibilidade. A configuração de entrada
`config/execucao.yaml` agora seleciona `relacionada_v1`, com K=1 e cache desligado:
compilação, testes mapeados e SAST global, sem T3/T4 amplos. Veja o
[escopo e tratamento das lacunas](docs/validacao_relacionada.md). Para
inspecionar a configuração alternativa sem iniciar API ou validação:

```bash
python executar.py --config config/execucao_otimizada.exemplo.yaml --mostrar-comando
```

O [roteiro](features/05-otimizacao-validacao/VALIDACAO.md) descreve os replays sem LLM.


A [auditoria das referências de desafios](docs/auditoria/avaliacao_referencias_codefixes.md)
avaliou 63 alternativas de correção em fixtures SAST isoladas, sem LLM e sem mudar
as regras ou o comparador. O relatório distingue limitações de pareamento,
associações amplas e remoção de alertas sem preservação funcional comprovada.

Novas execuções ampliadas usam o [comparador v2](docs/auditoria/comparador_v2.md),
com pareamento por tokens/contexto e motivos de indeterminação no painel. A reanálise
offline de 63 referências e oito patches preservou os artefatos antigos; novas
medições exigem outra execução, sem retomar contratos do comparador anterior.
