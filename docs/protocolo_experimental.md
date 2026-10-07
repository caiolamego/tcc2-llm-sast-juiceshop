# Protocolo experimental

## 1. Alvo

| Item | Valor |
|---|---|
| Projeto | OWASP Juice Shop |
| Versão | v20.1.1 |
| Fork utilizado | `https://github.com/caiolamego/juice-shop-tcc` |
| Commit fixado | `f915bddd82790d0f3018902d36ae9b4241a5f51f` ("Bump to v20.1.1") |
| Node.js exigido (`engines`) | `22 - 26` |
| Node.js confirmado no ambiente | `v26.7.0` (confirmado em 2026-10-07; dentro da faixa exigida) |
| npm | `11.19.0` |
| Python | `3.11.16` |
| git | `2.50.1` |

**Correção de registro (2026-10-07).** Versões anteriores deste documento citavam o commit `8ff89794d2188005e23ed0649aadb7b6faae1b36`, que **não existe** no espelho `workspace/juice-shop.git` (`git cat-file` retorna `could not get object info`). Era um hash transcrito incorretamente na documentação. O valor correto, confirmado por `git log` e já presente em `JUICESHOP_COMMIT` no `.env`, é `f915bddd…`. Todas as execuções realizadas (baseline SAST, medição de custos de validação, cenários de teste do runner) ocorreram sobre `f915bddd…`.

## 2. Ferramenta SAST e versionamento

| Item | Valor |
|---|---|
| Ferramenta | Semgrep |
| Versão | `1.177.0` — registrada em toda execução (Decisão D2) |
| Rulesets | `p/javascript`, `p/typescript`, `p/nodejs`, `p/expressjs`, `p/owasp-top-ten` |
| Flags fixas | `--json --no-git-ignore --metrics=off` |
| Modo de autenticação | **sem login** (execução anônima) |
| Worktree de referência | `workspace/wt-1` |

**Risco de não-versionamento conhecido e aceito (D2):** os rulesets do registro não são versionados — podem mudar sem aviso entre execuções em datas diferentes. Mitigação: a versão do Semgrep é registrada em toda execução e o JSON bruto (`outputs/sast_antes/baseline_raw.json`) é arquivado como fonte primária.

**Achado adicional (F3.2):** o Semgrep aplica uma lista de exclusão padrão embutida no próprio binário (reportada como `.semgrepignore patterns`, 1444 arquivos na execução de referência) mesmo sem nenhum `.semgrepignore` explícito no projeto. Essa lista não é controlada por `config/semgrepignore` e está sujeita ao mesmo risco de mudança entre versões.

**Achado adicional (F5, 2026-10-07) — campos indisponíveis sem login.** Na execução anônima, o Semgrep **não** preenche dois campos do JSON: `extra.fingerprint` e `extra.lines` retornam literalmente a string `requires login`. Consequências e tratamento na Seção 6.

## 3. Protocolo de filtragem (determinístico, aplicado antes de qualquer chamada à LLM)

1. **Excluir caminhos** — `config/semgrepignore`, convertido em flags `--exclude` (uma por linha, não existe flag de arquivo único — ver caderno, entrada de 2026-09-24):
   ```
   node_modules/, build/, dist/, frontend/dist/, frontend/node_modules/,
   coverage/, test/, data/static/codefixes/, vagrant/, screenshots/,
   logs/, frontend/src/assets/private/three.js, .github/, .npmrc,
   *.min.js, *.map
   ```
   `data/static/codefixes/` é excluído especificamente como mitigação de contaminação de treinamento (Parte 0, Risco 3). `logs/` e `three.js` foram adicionados após identificar, na execução de referência, que eram respectivamente um artefato de runtime e uma biblioteca de terceiros vendorizada — nenhum dos dois é código-fonte da aplicação. `.github/` e `.npmrc` foram adicionados após a execução de F3.6 revelar que 9 dos 21 findings elegíveis (43%) caíam em workflows de CI/CD e configuração do npm — a mesma fronteira de escopo do Adendo M1 (vulnerabilidades de supply chain/dependências fora do escopo), só identificada mais tarde porque os rulesets usados cobrem YAML incidentalmente. Nenhum dos dois é testável pela suíte automatizada do Juice Shop.

2. **Manter apenas findings de `metadata.category == "security"`.**

3. **Manter apenas os dois níveis mais críticos de severidade**, cobrindo os dois esquemas do Semgrep que coexistem na mesma execução (achado do caderno, entrada de 2026-09-25): `ERROR`/`WARNING` (esquema legado) e seus equivalentes `HIGH`/`MEDIUM`/`CRITICAL` (esquema atual de 4 níveis). Exclui-se apenas o nível mais baixo em qualquer um dos dois (`INFO`/`LOW`).

4. **Manter apenas findings com CWE mapeada** em `metadata.cwe`.

5. **Deduplicar por `(check_id, path)`** — mesma regra no mesmo arquivo conta uma vez.

6. **Amostragem estratificada por categoria OWASP** (não acionada nesta execução — 12 findings elegíveis, bem abaixo de qualquer `N_max` calculado em F2.4).

### Resultado da execução de referência

> **Nota de reconciliação.** A primeira exclusão de `.github/`/`.npmrc` derrubou os findings brutos de 30 para 15 (queda de 15, não os 9 esperados pela contagem pós-dedupe da execução anterior). Reconciliado: dos 30 brutos originais, 15 já eram código de aplicação (idênticos aos 15 desta execução) e 15 eram de `.github/`/`.npmrc`, dos quais só 9 sobreviviam à deduplicação (6 eram duplicatas internas, mesma regra disparando mais de uma vez no mesmo arquivo de workflow). As siglas `CMDI` e `INTEGRITY` desapareceram por completo da lista final — 100% dos achados dessas duas categorias estavam em configuração de CI/CD, nenhum na aplicação.

| Etapa | Contagem |
|---|---|
| Findings brutos (após exclusão de caminhos, incl. `.github/`/`.npmrc`) | 15 |
| Duplicatas removidas (passo 5) | 3 |
| Após deduplicação | 12 |
| Elegíveis após filtragem completa (passos 2–4) | 12 |
| Excluídos | 0 |
| Fora do código de aplicação | 0 |
| Com marcador `vuln-code-snippet` (ground truth parcial) | 5 de 12 |

## 4. Taxonomias e mapeamentos

### 4.1 CWE → sigla de vulnerabilidade (`config/mapa_cwe_vuln.yaml`)

Doze siglas definidas a priori (Decisão D7, a partir do referencial teórico do TCC 1), mais sete adicionadas após rodar o baseline real e encontrar CWEs não previstas (caderno, entrada de 2026-09-25: `CWE-95`, `CWE-73`, `CWE-1357`, `CWE-353`, `CWE-829`, `CWE-601`, `CWE-548`). Duas das adições reaproveitam siglas existentes (mesma família); três (`CWE-1357`, `CWE-353`, `CWE-829`) formaram a sigla `INTEGRITY`, que **não aparece no catálogo final** — todos os achados dessa sigla estavam em `.github/`/`.npmrc`, fora de escopo. A sigla permanece no mapa para o caso de reexecuções com outros rulesets, mas não demanda documento de RAG.

### 4.2 OWASP 2021 → OWASP 2025 (`config/mapa_owasp.yaml`)

O Semgrep rotula findings na numeração OWASP 2021; o referencial teórico do TCC usa a numeração 2025. Tabela de conversão confirmada contra a publicação oficial (`https://top10.owasp.org/2025/`):

| 2021 | 2025 | Observação |
|---|---|---|
| A01 Broken Access Control | A01 | Absorve SSRF (A10:2021) |
| A02 Cryptographic Failures | A04 | |
| A03 Injection | A05 | |
| A04 Insecure Design | A06 | |
| A05 Security Misconfiguration | A02 | |
| A06 Vulnerable and Outdated Components | A03 | Renomeada: Software Supply Chain Failures |
| A07 Identification and Authentication Failures | A07 | Renomeada: Authentication Failures |
| A08 Software and Data Integrity Failures | A08 | |
| A09 Security Logging and Monitoring Failures | A09 | Renomeada: Security Logging and Alerting Failures |
| A10 Server-Side Request Forgery | A01 | Absorvida por Broken Access Control |
| — | A10 | Categoria nova: Mishandling of Exceptional Conditions (sem equivalente 2021) |

A categoria registrada é **a declarada pelo Semgrep em `metadata.owasp`**, convertida pela tabela acima — não uma reclassificação nossa. Quando a categoria declarada parecer discutível para a CWE do finding (por exemplo, um path traversal rotulado como Insecure Design em vez de Broken Access Control), o valor original é preservado e a divergência é anotada na análise, para não introduzir julgamento manual no meio do pipeline.

### 4.3 Sigla → categoria de RAG (`config/mapa_categoria_rag.yaml`)

Mapeia cada sigla de vulnerabilidade a um dos 7 documentos de `knowledge_base/` (F5.4), com resolução em cascata: CWE específica → categoria OWASP → `generico.md`. Cada tentativa registra **qual arquivo foi efetivamente recuperado**.

## 5. Ground truth parcial (F3.5)

Findings cuja faixa de linhas cai dentro de um bloco `// vuln-code-snippet start/end <desafio>` do próprio Juice Shop são marcados com o nome do desafio em `marcador_juiceshop`. Isso não é uma lista exaustiva de vulnerabilidades reais (o Juice Shop tem falhas não demarcadas), mas todo marcador presente confirma uma vulnerabilidade intencional conhecida — usado na análise de resultados para distinguir findings sobre vulnerabilidades confirmadas de findings incidentais.

## 6. Assinatura de findings e critério R

O critério **R** (o alerta original deixou de ser detectado após a correção) exige comparar findings entre duas execuções do SAST. A Decisão D6 previa usar o `fingerprint` do Semgrep como assinatura estável, por ser independente do número de linha — que muda quando o patch é aplicado.

**Impedimento encontrado (2026-10-07).** Na execução anônima, `extra.fingerprint` vale `requires login` em todos os findings. Usar esse valor como assinatura torna os 12 findings indistinguíveis entre si, o que invalidaria o R.

**Decisão.** A assinatura passa a ser `sha256(check_id + "|" + caminho_relativo)`. Justificativa: o passo 5 da filtragem já deduplica por `(check_id, path)`, portanto esse par é único dentro do catálogo por construção. O número de linha não entra, mantendo a propriedade de estabilidade que a D6 buscava.

Consequências registradas:

- A comparação é feita no nível **regra × arquivo**, não em ocorrência individual. Se um arquivo tiver duas ocorrências da mesma regra em linhas diferentes e a correção resolver apenas uma, `R = 0`. É um critério conservador (nunca superestima o sucesso), e está declarado nas Limitações.
- `extra.lines` também retorna `requires login`, de modo que o trecho de código não vem da ferramenta. O trecho exigido pela Seção 3.5 do TCC 1 passa a ser extraído diretamente do arquivo no worktree, a partir de `path`, `start.line` e `end.line`, no momento da montagem do catálogo.
- Autenticar no Semgrep (`semgrep login`) restauraria os dois campos, mas acrescentaria dependência de serviço externo e risco de variação de comportamento no meio do experimento. **Não adotado**, pelo mesmo princípio da D2.

## 7. Validação das correções

Escada de camadas (Decisão D5), executada em ordem, interrompendo na primeira falha:

| Camada | Comando | Papel |
|---|---|---|
| T0 | `npx tsc --noEmit` | Compilação/tipos |
| T2 | teste unitário do arquivo alterado, quando existe correspondência por nome | Verificação local rápida |
| T3 | `npm run test:server` | Testes unitários do servidor (335 testes) |
| T4 | `npm run test:api` | Testes de integração da API (555 testes) |

Condições fixas de execução:

- `TZ=UTC` em todo subprocesso (caderno, 2026-09-17): o Juice Shop tem um teste de data que falha em fusos negativos.
- `PORT` distinta por worktree (`wt-N` → `3100+N`). Os testes de API não sobem servidor HTTP — criam o app em memória com SQLite `:memory:` — mas importar `server.ts` dispara `validatePreconditions`, que encerra o processo se a porta estiver ocupada.
- Timeout obrigatório em todo subprocesso; estouro é registrado como falha com motivo `timeout`.
- **Limite de paralelismo em T4:** `test/api/chat.test.ts` abre um servidor auxiliar em porta fixa (43210), sem variável de ambiente. Enquanto isso não for contornado, **T4 não roda em paralelo** — a camada é serializada entre worktrees.

### 7.1 Linha de base de testes (referência para o critério F)

A suíte do Juice Shop **não passa integralmente** no commit fixado, sem nenhuma alteração: `test/api/internet-resources.test.ts` faz uma requisição real ao StackOverflow, que responde `403` de forma consistente no ambiente utilizado. Um critério F definido como "nenhum teste falhou" tornaria `F = 0` para toda e qualquer correção, zerando a TRV por motivo alheio ao experimento.

**Decisão.** `F = 1` quando o conjunto de testes que falham após a correção está **contido** no conjunto que já falhava sem alteração alguma. A linha de base é gerada uma vez por `scripts/baseline_testes.py`, versionada em `outputs/baseline_testes.json` com commit do alvo, data e nome de cada teste falho, e reconferida a cada mudança de ambiente.

Vantagens sobre pular o teste pelo nome: cobre qualquer teste instável ou dependente de rede sem precisar enumerá-los, e deixa registrado no repositório o estado exato do alvo. Custo: uma execução de referência (~12 s).

Linha de base medida em 2026-10-07, commit `f915bddd…`, Node `v26.7.0`: **T3 sem falhas** (335 testes); **T4 com uma falha**, o teste de rede do StackOverflow (`test/api/internet-resources.test.ts`, HTTP 403). Os nomes dos testes falhos vêm do relatório JUnit do Node. O runner se recusa a validar se a linha de base registrada for de outro commit.

Cada tentativa registra `testes_falhos_novos` (os que falharam além da linha de base). Esse campo alimenta a separação entre os conjuntos **F** (falha funcional real) e **D** (teste de desafio do Juice Shop que falha justamente porque a vulnerabilidade foi corrigida — Risco 2 da Parte 0). A classificação de cada teste novo em F ou D é feita na análise, sobre o número reduzido de correções aceitas, e não automaticamente dentro do pipeline.

### 7.2 Testes intermitentes: reexecução com interseção

Mesmo com a linha de base, observou-se um teste de T4 que falha de forma intermitente sem nenhuma alteração no código: `test/api/erasure-request.test.ts` (`POST erasure request does not actually delete the user`) falhou 1 vez em 8 execuções, com `socket hang up`. Como não consta da linha de base, uma ocorrência isolada reprovaria indevidamente uma correção válida.

**Decisão.** Quando uma camada acusa testes falhos novos, ela é **executada uma segunda vez**, e o conjunto considerado real é a **interseção** dos testes falhos novos das duas execuções. Um teste precisa falhar nas duas rodadas para contar contra o F. Cada validação registra `reexecucoes` e `testes_falhos_intermitentes` (os que falharam em apenas uma das rodadas).

Por que não ampliar a linha de base com várias execuções e unir as falhas: isso colocaria `erasure-request` permanentemente na lista de falhas toleradas, e uma correção que de fato quebrasse esse teste passaria como se nada tivesse ocorrido. A reexecução preserva a sensibilidade do critério; a união da linha de base a destruiria. Custo: uma execução extra de T4 (~12 s) apenas nos casos em que há falha nova.

## 8. Rastreabilidade

Toda execução do baseline gera: `outputs/sast_antes/baseline_raw.json` (saída bruta do Semgrep, arquivada), `outputs/sast_antes/catalogo_issues.json` (todos os findings, elegíveis e excluídos, com motivo), `outputs/sast_antes/catalogo_meta.json` (contagens por etapa, versão do Semgrep, rulesets e **commit do alvo**), `outputs/sast_antes/relatorio_baseline.md` (agregações para o caderno). O commit do alvo é registrado também em cada linha de `outputs/resultados_consolidados/execucoes.jsonl` e em cada artefato de validação, para que nenhum resultado dependa apenas deste documento.

## 9. Modelo de linguagem e custos

| Item | Valor |
|---|---|
| Modelo | `gpt-4.1-mini` |
| Temperatura | `0` |
| `seed` | fixa, definida no `.env` |
| Formato de resposta | JSON em modo estrito (schema com `additionalProperties: false`, todos os campos obrigatórios) |
| Preço de entrada | US$ 0,40 por milhão de tokens |
| Preço de saída | US$ 1,60 por milhão de tokens |
| Fonte do preço | página oficial de preços da OpenAI, consultada em 2026-10-07; registrada em `config/precos_llm.yaml` |
| Guarda de orçamento | `MAX_LLM_CALLS` e `MAX_USD` no `.env`; contador persistido em `.cache/orcamento_llm.json` |

Respostas são cacheadas em disco por `sha256(prompt + modelo + seed)`; respostas servidas do cache não são contabilizadas no orçamento. `temperature=0` e `seed` fixa reduzem, mas não eliminam, a variação entre execuções — `system_fingerprint` é registrado em cada tentativa para detectar mudança de infraestrutura do provedor.

Custo medido na primeira chamada real (2026-10-07, caso `JS003`, estratégia `P1`): modelo `gpt-4.1-mini-2025-04-14`, `system_fingerprint` `fp_adba1d049a`, 640 tokens de entrada, 548 de saída, 6,2 s, **US$ 0,00113**. Extrapolando para 12 vulnerabilidades × 4 estratégias, a execução completa fica na ordem de **US$ 0,05**. O orçamento não é fator limitante neste experimento; o fator limitante é o tempo de calendário.

## 10. Congelamento das restrições de prompt

As restrições presentes em todos os prompts (F5.3 do guia) foram **fixadas antes da execução completa** e são idênticas para as quatro estratégias, de modo que a comparação entre P1–P4 isole o que se pretende variar (contexto recuperado e raciocínio guiado) e não o rigor das instruções.

**Ajuste registrado (2026-10-07), anterior à execução completa.** A primeira chamada real expôs uma ambiguidade na restrição "altere o mínimo necessário": o modelo produziu uma barreira correta contra path traversal, mas reescreveu também a mensagem de erro da rota, quebrando um teste que verifica a string exata. A restrição foi então explicitada: **não alterar mensagens de erro, textos visíveis ao usuário, nomes de identificadores nem assinaturas de funções existentes**. A redação é genérica e vale para qualquer caso — não foi escrita para o caso `JS003`.

Condições que tornam esse ajuste legítimo e não seleção de resultados favoráveis:

1. Foi feito **antes** da execução completa, com base em uma única tentativa exploratória, e vale igualmente para os 12 casos e as 4 estratégias.
2. A tentativa que motivou o ajuste está arquivada em `outputs/tentativas/JS003_A06_PATHTRAV_P1_E01_*` e é reportada no texto como observação preliminar, não descartada.
3. Após esta data, **nenhuma alteração de prompt é feita com base em resultados da execução completa**. Qualquer necessidade identificada depois entra como trabalho futuro.

A observação em si é resultado: a correção removeria o alerta do SAST (`R = 1`) e seria classificada como bem-sucedida por qualquer avaliação baseada apenas em reanálise estática, mas foi reprovada na camada de testes por uma alteração cosmética. É evidência direta do argumento central do trabalho — remoção de alerta não é prova de correção adequada — e deve ser citada no capítulo de discussão.