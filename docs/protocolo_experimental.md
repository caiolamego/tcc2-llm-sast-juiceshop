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

**Extensão para timeout (2026-10-08, antes da E02).** Na primeira sessão da E01, o T4 de um worktree sem alteração travou em `test/api/password.test.ts` até o limite de 300 s e passou em 11 s nas duas execuções seguintes (caderno, 2026-10-08). Um travamento desses durante uma tentativa daria `F = 0` sem relação com a correção. Por isso, **timeout também dispara uma reexecução da camada, uma única vez** (T0, T2, T3 e T4). Como a primeira rodada não gera relatório, não há interseção possível: vale o resultado da segunda rodada sozinha. Se a segunda também estourar o tempo, a camada reprova com motivo `timeout`; se a segunda acusar testes falhos novos, eles contam. Cada camada registra `timeout_na_primeira_rodada` e `reexecucoes`.

### 7.3 Limitação do oráculo R conforme o tipo de regra

O critério R depende de a regra do Semgrep deixar de disparar após a correção. Isso não depende só da correção: depende de **como a regra decide**. A primeira hipótese (separar regras `audit` de `vuln`) não se sustentou nos dados: `metadata.subcategory` vale `vuln` para os 12 achados elegíveis, enquanto 9 deles têm `.audit.` no `check_id`. Os dois critérios discordam e nenhum descreve o mecanismo de decisão.

**Classificação adotada: modo da regra e saneadores declarados.** Lida no código-fonte das 7 regras distintas, versionado como cópia de referência em `config/semgrep-rules-referencia/` (repositório `semgrep/semgrep-rules`, ramo `develop`, commit `a84ff9cc`, copiado em 2026-10-07; pode divergir das regras que o registro executou, ver README da pasta). Registrada no catálogo nos campos `modo_regra` e `saneadores_regra`.

| Faixa | Mecanismo | Casos | Proporção |
|---|---|---|---|
| 1. `search` | Casamento de padrão, sem fluxo de dados. O alerta só some se o padrão sumir do código. | JS012 | 1 de 12 |
| 2. `taint` com saneadores declarados | Rastreia o dado da origem (requisição) ao uso; aceita `parseInt(...)` e `.hash(...)` como limpeza. | JS005, JS009 | 2 de 12 |
| 3. `taint` sem saneadores declarados | Rastreia o fluxo, mas nenhuma função conta como limpeza e validações condicionais (`if`) não são consideradas. O alerta só some se o fluxo for interrompido ou se a forma do uso mudar para uma que a regra exclui. | JS001–JS004, JS006–JS008, JS010, JS011 | 9 de 12 |

**Sondagens sem LLM (2026-10-07), regra `express-res-sendfile`, faixa 3.** Resultados em `outputs/sondagens/`:

- **A. Tentativas da LLM em JS003:** o alerta **persiste nas duas**. `EXP01` (verificação `startsWith` do caminho resolvido) e `EXP02` (bloqueio de `..`) têm `R = 0`, embora a `EXP02` passe em toda a validação. As duas são validações condicionais, que a regra não considera.
- **B. Correção escrita à mão** (não gerada pela LLM e fora de qualquer métrica), na forma que a regra exclui: `res.sendFile(file, { root: ... })`, mantendo a validação e a mensagem de erro. O alerta **desaparece** (`R = 1`) nos 4 casos de `sendFile`, sem alertas novos. Na validação:
  - JS004 e JS007: passam em todas as camadas (não há teste unitário para esses arquivos).
  - JS003 e JS002: reprovam no T2. Os testes unitários (`keyServer`, `fileServer`) conferem, por mock, que o primeiro argumento de `sendFile` contém o caminho completo (`encryptionkeys/…`, `ftp/…`). No JS002 isso inclui 5 testes de desafio. Rodado à parte, só para diagnóstico, o T4 passa nos dois: o comportamento HTTP se mantém.

**Consequências para a análise.** A definição da TRV (Seção 3.9 do TCC 1) **não muda**. Muda a análise:

1. Os resultados são reportados também **separados pelas três faixas**. Na faixa 3, `R = 0` pode refletir a forma como a regra decide e não a ausência de correção.
2. Há casos em que R e F puxam para lados opostos: a forma que zera o alerta quebra testes unitários acoplados à implementação, e a forma que preserva os testes não zera o alerta. Os casos de `sendFile` com teste unitário (JS002, JS003) são o exemplo concreto.
3. Para permitir essa análise, cada tentativa registra a saída completa do SAST posterior (F6).

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
2. A tentativa que motivou o ajuste está arquivada em `outputs/tentativas/JS003_A06_PATHTRAV_P1_EXP01_*` (renomeada de `E01` em 2026-10-07, para deixar `E01` livre para a execução oficial; a tentativa seguinte, já com a restrição, é a `EXP02`) e é reportada no texto como observação preliminar, não descartada.
3. Após esta data, **nenhuma alteração de prompt é feita com base em resultados da execução completa**. Qualquer necessidade identificada depois entra como trabalho futuro.

A observação em si é resultado, mas não é uma divergência entre R e F: a sondagem A (Seção 7.3) mostrou que o alerta **persiste nas duas tentativas** (`R = 0` na EXP01 e na EXP02), porque a regra `express-res-sendfile` não reconhece verificações condicionais. O que as duas tentativas mostram é a **troca entre profundidade da correção e preservação funcional**: a correção reprovada (EXP01) também verificava, com `startsWith`, se o caminho resolvido permanece dentro de `encryptionkeys/`; a aceita nos testes (EXP02), escrita sob a restrição de mudança mínima, só bloqueia `..` e `/`, e é defensivamente mais fraca. A restrição elevou a preservação funcional e reduziu a profundidade da correção. Esse efeito deve ser citado no capítulo de discussão sobre engenharia de prompt.

A divergência entre R e F, isto é, remoção do alerta sem aprovação nos testes, é ilustrada pelos casos **JS005, JS006 e JS011 da execução preliminar E01**, que têm evidência real. Em JS005 e JS006, a consulta parametrizada remove o alerta de SQL injection (`R = 1`, `M = 1`) e reprova no T4 só nos testes de `login.test.ts` que executam o ataque e esperam que ele funcione. Em JS011, a correção remove o alerta e reprova só no teste que espera o payload de SSTI ser avaliado. É evidência direta do argumento central do trabalho: remoção de alerta não é prova de correção adequada, e aprovação nos testes também não é, quando os testes verificam a própria vulnerabilidade.

## 11. Limitações

### L1. Conflito entre R e F em JS002 e JS003, identificado antes da E01

Na sondagem B (Seção 7.3, `outputs/sondagens/B_*_ESCRITO_A_MAO*`), feita à mão e **antes da execução E01**, a forma `res.sendFile(x, { root: ... })` foi a única que a regra `express-res-sendfile` reconhece como segura: ela remove o alerta (`R = 1`) nos quatro casos de `sendFile`. Em **JS002** e **JS003**, porém, essa forma reprova no T2: os testes unitários (`fileServer.unit.test.ts`, `keyServer.unit.test.ts`) verificam, por mock, que o primeiro argumento passado ao `sendFile` é o caminho completo (`ftp/…`, `encryptionkeys/…`). Rodado à parte, só para diagnóstico, o T4 passa nos dois casos, o que confirma que o comportamento HTTP se mantém.

Consequência: **nesses dois casos nenhuma correção consegue satisfazer R e F ao mesmo tempo.** A forma que remove o alerta quebra o teste unitário, e as formas que preservam o teste (validação condicional do nome do arquivo) não removem o alerta, porque a regra é `taint` sem saneadores declarados (faixa 3).

**O critério F não foi alterado por causa disso.** O T2 continua contando; nenhum teste foi pulado, removido ou acrescentado à linha de base. O tratamento é só na análise: os casos são separados pelo `tier_falha` e pelos `testes_falhos_novos`, já registrados em cada linha do `execucoes.jsonl`, de modo que uma reprovação em JS002 ou JS003 causada por esses testes unitários possa ser lida como efeito do acoplamento entre teste e implementação, e não como defeito funcional da correção. As correções escritas à mão da sondagem B não entram em nenhuma métrica.

## 12. Condição de diagnóstico P1L (localização do alerta)

**O que é.** `P1L_diagnostico_localizacao` é o prompt `P1_simples` mais um único bloco com a localização e a identificação do alerta do Semgrep: arquivo, linha, regra (`check_id`), CWE e mensagem. O bloco entra entre o código e as restrições, na mesma posição em que o P2 insere o roteiro. Todo o resto é idêntico ao P1 (papel, tarefa, código, restrições congeladas da Seção 10, formato).

**O que não é.** **Não é uma estratégia nova do desenho experimental.** As estratégias P1 a P4 do TCC 1 não mudam e a TRV do desenho continua calculada só sobre elas. O P1L é uma **condição de diagnóstico**: serve para medir o efeito de o prompt não dizer qual vulnerabilidade corrigir.

**Justificativa.** A confusão foi prevista **antes de qualquer execução**, no Adendo M4: nas estratégias sem alerta (P1, P2), quem escolhe o que corrigir é a LLM, e não o SAST; o critério R, porém, só verifica o alerta escolhido pelo SAST. A execução preliminar E01 mostrou o efeito nos dados (caderno, 2026-10-08): em JS001 a LLM corrigiu outra vulnerabilidade do mesmo arquivo, e JS005/JS006 e JS009/JS010 receberam prompts idênticos, por serem regras diferentes no mesmo ponto do mesmo arquivo. Comparar P1 com P1L, caso a caso, isola o efeito da informação de localização, sem alterar o desenho aprovado.

**Execução.** O P1L roda **sempre e fora da cadeia** de estratégias (`--diagnosticos P1L`): não depende de P1 ou P2 terem sido aceitos e não interrompe a cadeia. Assim, existe um par P1 × P1L para todos os casos. Cada linha do `execucoes.jsonl` registra `condicao` (`desenho` ou `diagnostico`), e as métricas do desenho excluem as linhas de diagnóstico, que são reportadas à parte.

## 13. Separação dos conjuntos F e D: definição, operacionalização e análise de sensibilidade

> **Nota de transparência sobre a ordem dos fatos.** A definição do conjunto D estava pré-registrada (Seção 7.1) antes de qualquer execução, mas **não foi implementada a tempo da execução preliminar E01**. A operacionalização abaixo foi construída **depois** de a E01 ter rodado e de termos visto quais testes falharam nela. A sequência real está descrita a seguir, sem reordenar.

**1. Definição pré-registrada (Seção 7.1).** D é o conjunto de testes do Juice Shop que falham justamente porque a vulnerabilidade foi corrigida; uma correção não perde F por fazer cair um teste de D. A classificação seria feita na análise. Até a E01, nenhuma regra operacional existia.

**2. Execução preliminar E01 (2026-10-08), sem separação.** Os testes que derrubaram correções com `R = 1` foram, entre outros, os de `login.test.ts` que executam SQL injection e esperam token (JS005, JS006) e o de `user-profile.test.ts` que espera o payload de SSTI avaliado (JS011). A E01 fica arquivada como preliminar.

**3. Primeira tentativa: marcador de desafio (2026-10-08).** Procurou-se um marcador mecânico na suíte. O encontrado foi a asserção de desafio resolvido, `assert.equal(challenges.<id>.solved, true)` (32 ocorrências) e duas variantes (`challenge.solved, true` e `'Challenge successfully solved'`). A busca por palavras no nome do teste foi descartada, porque pega testes que afirmam a defesa ("is caught by parser", "is not susceptible", "cannot be bypassed"). A comparação com as correções oficiais (`data/static/codefixes/`) foi descartada, porque só existe para 5 dos 12 casos.

**4. Por que o marcador se mostrou incompleto.** Ao aplicá-lo aos testes que falharam na E01, viu-se que os **testes de exploit da API não citam desafio**: o teste de SQL injection exige HTTP 200 com token para a carga de ataque, e o de SSTI exige o resultado da expressão avaliada. Pela semântica, eles dependem da vulnerabilidade; pelo marcador, seriam F. O marcador era só uma forma de operacionalizar a definição da 7.1, e não a definição.

**5. Critérios (2026-10-09), escritos antes de classificar qualquer teste** (`docs/criterios_conjunto_d.md`). Um teste pertence a D se, e somente se, suas asserções só podem valer enquanto a vulnerabilidade está presente, verificado por uma de três formas:
- **(a)** asserção de desafio resolvido (as três variantes do item 3);
- **(b)** requisição com carga de ataque conhecida recebendo resposta de sucesso (2xx, token de autenticação, ou dado que não deveria ser acessível sem a falha);
- **(c)** resposta contendo evidência de que a carga foi interpretada (avaliação de template, vazamento de erro de SQL, execução ou entrega sem neutralização de script).

Todo o resto é F, inclusive testes que afirmam que a defesa funciona ou que a aplicação não é suscetível. Testes baseados em mock do caminho de chamada (por exemplo, o argumento passado a `res.sendFile`) são F. Em dúvida, F.

**6. Construção a priori da lista sobre a suíte inteira** (`docs/conjunto_d.md`, `config/conjunto_d.json`, gerados por `scripts/gerar_conjunto_d.py`). Foram varridos **863 blocos `it(...)`** de `test/api/` e `test/server/` inteiros (os ~27 testes gerados em laço são funcionais e ficam em F). O critério (a) é aplicado mecanicamente; para (b) e (c), os candidatos foram localizados por sinais de carga de ataque no corpo e por palavras-chave no nome, e decididos pelas asserções. Resultado: **75 testes em D** — 36 por (a), 29 por (b), 10 por (c) — e 35 testes examinados e mantidos em F, com o motivo. Doze deles estão **sinalizados**: parecem depender de uma falha, mas ficam fora da letra dos critérios (listagem de diretório e log de acesso obtidos por GET simples, vazamento de erro que não é de SQL, ReDoS com 503, exportação sem CAPTCHA). Pela regra "em dúvida, F", ficam em F até decisão do grupo. A lista foi montada sobre a suíte, sem consultar os resultados da E01, mas quem a montou já conhecia os testes que tinham falhado na E01; essa familiaridade não pode ser apagada e fica declarada.

**7. Decisão: reportar nas duas definições (análise de sensibilidade).**
- **`d_marcador`:** só o critério (a). Regra mecânica, sem julgamento.
- **`d_criterio`:** os três critérios, pela lista do item 6. É a definição usada em `F` e `classificacao_final`, por ser a operacionalização mais fiel à 7.1.
- Cada validação grava também `F_sem_separacao` (qualquer falha nova reprova, como na E01), para comparação.
- Os conjuntos são encaixados (`d_marcador` ⊂ `d_criterio`), portanto `F_sem_separacao ≤ F_marcador ≤ F_criterio`. A escada de validação só para quando uma camada falha por algo fora de `d_criterio`, para que as três versões saiam da mesma validação.
- A cadeia de estratégias só para quando a tentativa é aceita **sem separação** (definição mais estrita). Nas métricas de cada definição, tentativas posteriores ao primeiro aceite **naquela definição** não entram, como se a cadeia tivesse parado ali.
- **TCD** (proporção de correções aceitas que fazem cair ao menos um teste de D) é calculada em cada definição; sem separação, é 0 por construção.

A diferença entre as métricas nas duas definições mede quanto do resultado depende da classificação.

