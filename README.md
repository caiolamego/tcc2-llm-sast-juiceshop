# Correção de vulnerabilidades em código com LLMs

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
| T2 | Testes unitários do arquivo alterado | Mocha |
| T3 | Suíte unitária de servidor | Mocha |
| T4 | Testes de API | Jest + Frisby |
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

Agregações disponíveis: geral, por estratégia de prompt, por caso, por categoria OWASP, por CWE e por classe de causa raiz.

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

./scripts/setup_target.sh 4 # clona o alvo e prepara 4 worktrees (demora)
```

---

## Uso

```bash
# 1. Análise estática inicial e catálogo de vulnerabilidades
python scripts/run_baseline_sast.py
python scripts/build_issue_catalog.py

# 2. Indexação da base de conhecimento (RAG)
python -m pipeline.rag.build_index

# 3. Execução do pipeline
python -m pipeline.run_pipeline --execucao E01                    # completa
python -m pipeline.run_pipeline --casos JS003,JS011 --execucao E01 # subconjunto
python -m pipeline.run_pipeline --dry-run                          # sem chamar a API

# 4. Confirmação dinâmica sobre as correções aceitas
python scripts/run_challenge_oracle.py --execucao E01

# 5. Consolidação de métricas (não chama a API)
python scripts/summarize_results.py
```

A execução é retomável: tentativas já concluídas são identificadas e puladas.

---

## Estrutura

```
config/           parâmetros do experimento, mapeamentos CWE/OWASP, pesos de severidade
docs/             protocolo experimental, modelo de dados, ADRs, caderno de laboratório
knowledge_base/   base documental do RAG (Markdown fragmentado por seção)
prompts/          templates das quatro estratégias
src/pipeline/     sast · target · llm · prompting · rag · patching · validation · metrics
scripts/          preparação do alvo, baseline, catálogo, consolidação
outputs/          artefatos gerados (ver docs/modelo-de-dados.md)
workspace/        clone do alvo e pool de worktrees (não versionado)
```

### Rastreabilidade dos artefatos

Cada tentativa recebe um identificador único que nomeia todos os seus artefatos, dispensando banco de dados — o nome do arquivo é a chave estrangeira.

```
<CASO>_<OWASP>_<VULN>_<PROMPT>_<EXECUCAO>_<ARTEFATO>.<ext>

JS007_A05_SQLI_P3_E01_prompt.txt
JS007_A05_SQLI_P3_E01_resposta.json
JS007_A05_SQLI_P3_E01_sast_depois.json
```

O modelo de dados completo, com chaves, campos e relações, está em [`docs/modelo-de-dados.md`](docs/modelo-de-dados.md).

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
[`docs/auditoria_cobertura_semgrep.md`](docs/auditoria_cobertura_semgrep.md).
Esses resultados ainda nao substituem o baseline oficial de 12 casos.

A matriz exploratoria de desafios, alertas e triagem fica em
[`outputs/auditoria_sast/matriz_desafios.csv`](outputs/auditoria_sast/matriz_desafios.csv)
(versao completa em JSON). Ela preserva os 113 desafios no catalogo e distingue
alertas confirmados, falsos positivos e inconclusivos; nao altera os casos JS001-JS012.

A proposta de segunda coorte agrupa 20 desafios confirmados em 16 causas de
correcao, com quatro pilotos ainda dependentes de testes de seguranca e de
congelamento das regras. Ver
[`docs/selecao_exploratoria_correcao.md`](docs/selecao_exploratoria_correcao.md)
e [`outputs/auditoria_sast/candidatos_correcao.csv`](outputs/auditoria_sast/candidatos_correcao.csv).

A segunda rodada exploratoria acrescentou dois desafios com alerta confirmado
(senha fraca e metricas expostas): 44 alertas brutos no perfil ampliado,
22 desafios distintos confirmados. A triagem, os dois desafios investigados
sem nova regra e os comandos de reproducao estao em
[`docs/auditoria_rodada2.md`](docs/auditoria_rodada2.md). Nenhum resultado da
LLM foi produzido nesta rodada.

A terceira rodada delimitada identificou mais um desafio com alerta confirmado,
`resetPasswordMortyChallenge`, chegando a 45 alertas exploratorios brutos e
23 desafios distintos confirmados. Os dez desafios marcados que permanecem
sem alerta confiavel e as limitacoes de deployment estao em
[`docs/auditoria_rodada3.md`](docs/auditoria_rodada3.md). Isso ainda nao
substitui o baseline do experimento principal.

Uma quarta rodada expandiu a busca para desafios sem marcador e confirmou
mais cinco, chegando a 51 alertas exploratorios brutos e 28 desafios
distintos. A triagem (inclusive um falso positivo), os quatro padroes de regra
e as limitacoes estao em
[`docs/auditoria_rodada4.md`](docs/auditoria_rodada4.md).

A quinta rodada chegou a **56 alertas exploratorios brutos e 31 desafios
distintos confirmados por revisao estatica**: 38 alertas confirmados, 16 falsos
positivos e 2 inconclusivos. Foram acrescentados acesso a outra cesta e dois
desafios B2B que compartilham o mesmo ponto de correcao. Detalhes e limites em
[`docs/auditoria_rodada5.md`](docs/auditoria_rodada5.md); matriz dessa rodada em
[`outputs/auditoria_sast/rodada5/matriz_desafios.csv`](outputs/auditoria_sast/rodada5/matriz_desafios.csv).
O baseline e a selecao antiga de candidatos para a LLM nao foram alterados.

A sexta rodada chegou a **59 alertas exploratorios brutos e 35 desafios
distintos confirmados por revisao estatica**: 41 alertas confirmados, 16 falsos
positivos e 2 inconclusivos. Sao tres alertas novos (cesta, senha atual e
CAPTCHA) e uma associacao adicional de SSTI a alertas existentes, sem inflar
a contagem bruta. A [matriz dessa rodada](outputs/auditoria_sast/rodada6/matriz_desafios.csv)
e o [relatorio da rodada 6](docs/auditoria_rodada6.md) registram evidencias,
revisoes, o scan completo com timeout de 30 segundos e proximos candidatos.
Baseline e snapshots anteriores permanecem intactos; nenhuma LLM foi executada.

A setima rodada chegou a **64 alertas exploratorios brutos e 37 desafios
distintos confirmados**: 43 alertas confirmados, 19 falsos positivos e 2
inconclusivos. Acrescentou autoria de avaliacoes e promocao Deluxe sem validar
modo de pagamento, com revisao dos fluxos e testes isolados das rotas reais
usando dependencias simuladas. A [matriz atual](outputs/auditoria_sast/rodada7/matriz_desafios.csv)
e o [relatorio da rodada 7](docs/auditoria_rodada7.md) incluem os tres falsos
positivos novos e os limites dos testes. Nenhum baseline ou candidato antigo
de correcao foi alterado; nenhuma LLM foi executada.

A oitava rodada incluiu os quatro candidatos priorizados: exportacao de dados,
quantidade negativa, cadastro administrativo e autoria de feedback. O perfil
acumulado chegou a **68 alertas brutos e 41 desafios distintos confirmados**:
47 alertas confirmados, 19 falsos positivos e 2 inconclusivos. A
[matriz da rodada 8](outputs/auditoria_sast/rodada8/matriz_desafios.csv) e o
[relatorio](docs/auditoria_rodada8.md) distinguem testes HTTP com API gerada e
SQLite reais dos testes com dependencias simuladas. A expansao para aqui,
conforme o pedido de quatro candidatos; baseline, selecao antiga de correcao
e resultados anteriores permanecem intactos. Nenhuma LLM foi executada.

A nona rodada confirmou leitura local via `layout` e alteracao anonima de
produtos: **72 alertas brutos e 43 desafios distintos confirmados**, com
49 alertas confirmados, 21 falsos positivos e 2 inconclusivos. A
[matriz da rodada 9](outputs/auditoria_sast/rodada9/matriz_desafios.csv) usa
o scan completo, nao a primeira tentativa com timeout. O
[relatorio](docs/auditoria_rodada9.md) documenta integracao local com hbs e
API gerada reais, controles, falsos positivos e limites. Nenhuma LLM foi
executada; o baseline e a selecao antiga para correcao permanecem intactos.

A decima rodada confirmou falsificacao de cupons e validade baseada em data
do cliente: **74 alertas brutos e 45 desafios distintos confirmados**, sendo
51 alertas confirmados, 21 falsos positivos e 2 inconclusivos. A
[matriz da rodada 10](outputs/auditoria_sast/rodada10/matriz_desafios.csv) e o
[relatorio](docs/auditoria_rodada10.md) registram testes isolados do codigo real
e scans repetidos. Oito dos dez prioritarios foram incluidos, encerrando a
expansao pela meta de cobertura. A consolidacao da selecao versionada de
causas para correcao ainda esta pendente; nenhuma LLM foi executada.

A rodada 11, solicitada como expansao adicional, chegou a **76 alertas brutos
e 47 desafios distintos confirmados** (53 alertas confirmados, 21 falsos
positivos, 2 inconclusivos). Confirmou concorrencia em curtidas com MarsDB
real e JSONP **condicionado a origem atacante no mesmo site**: o controle
cross-site com cookie Lax nao vazou email. A
[matriz](outputs/auditoria_sast/rodada11/matriz_desafios.csv) e o
[relatorio](docs/auditoria_rodada11.md) registram o teste de navegador,
precondicoes e limites; nao houve LLM ou alteracao do baseline.

A rodada 12 atingiu **50 desafios distintos confirmados**, com 78 alertas
brutos (55 confirmados, 21 falsos positivos e 2 inconclusivos). Acrescentou
cadastro vazio, confirmacao de senha divergente e avaliacao zero, demonstrados
por HTTP e persistencia no SQLite. Dois alertas cobrem esses tres desafios,
sem equivaler automaticamente a tres causas independentes. A
[matriz](outputs/auditoria_sast/rodada12/matriz_desafios.csv) e o
[relatorio](docs/auditoria_rodada12.md) preservam condicoes e limitacoes
anteriores, incluindo JSONP same-site. Nenhuma LLM foi executada.

| Fase | Situação |
|---|:---:|
| Preparação do ambiente e do alvo | ⬜ |
| Baseline SAST e catálogo de issues | ⬜ |
| Workspace e validação em camadas | ⬜ |
| Camada LLM, prompts e RAG | ⬜ |
| Orquestração e métricas | ⬜ |
| Execução exploratória | ⬜ |
| Execução completa | ⬜ |
| Análise e redação | ⬜ |

---

## Licença

MIT. Ver [LICENSE](LICENSE).

O OWASP Juice Shop é distribuído sob licença própria e não é redistribuído neste repositório — é obtido em tempo de configuração a partir do repositório oficial, em commit fixado.
