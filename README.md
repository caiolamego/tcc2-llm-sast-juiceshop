# Correção de vulnerabilidades em código com LLMs

Pipeline automatizado que integra análise estática de segurança (SAST), Modelos de Linguagem de Grande Escala (LLMs), estratégias de contextualização e testes automatizados para gerar e **validar** correções de vulnerabilidades no OWASP Juice Shop.

Trabalho de Conclusão de Curso 2 — Engenharia de Software, Faculdade de Ciências e Tecnologias em Engenharia (FCTE), Universidade de Brasília.

**Autores:** Matheus de Siqueira Brant e Caio Magalhães Lamego
**Orientadora:** Profa. Dra. Elaine Venson
**TCC 1 (monografia):** [link]&nbsp;·&nbsp;**Prova de conceito:** [link]

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