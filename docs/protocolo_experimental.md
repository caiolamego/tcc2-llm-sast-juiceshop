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

**Decisão.** `F = 1` quando o conjunto de testes que falham após a correção está **contido** no conjunto que já falhava sem alteração alguma. A linha de base é gerada uma vez por `scripts/experiment/baseline_testes.py`, versionada em `outputs/baseline_testes.json` com commit do alvo, data e nome de cada teste falho, e reconferida a cada mudança de ambiente.

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

## 11. Catálogo ampliado por ocorrência — política escopo_apenas_v1

Implementado em 12/10/2026 na feature 01. Esta seção registra a política do conjunto ampliado;
as seções anteriores descrevem o catálogo histórico e as execuções E01/E02.

O gerador `scripts/experiment/build_expanded_catalog.py` lê as quatro fontes da auditoria
combinada arquivada, verifica hashes, commit, versão do Semgrep e associação por número,
regra, arquivo e intervalo. A decisão de escopo é a classificação arquivada validada.
O filtro histórico de severidade/categoria/CWE não é reaplicado ao conjunto ampliado.

A unidade é uma ocorrência (regra normalizada, arquivo e intervalo completo no commit fixado),
sem deduplicação ou agrupamento por causa. Entram confirmados, falsos positivos e inconclusivos;
só `fora_escopo` é excluído. O catálogo produzido contém 78 casos: 55 confirmados,
21 falsos positivos e 2 inconclusivos. Há 46 exclusões rastreáveis, totalizando 124 alertas.
A presença de um falso positivo permanece como metadado; eventual remoção de seu alerta
não será interpretada como prova de correção de uma vulnerabilidade real.

Os IDs `AMP…` derivam de SHA-256 sobre commit, regra, arquivo e coordenadas. Eles identificam
ocorrências no baseline; deslocamentos de linhas após patches exigirão tratamento na integração.
Trechos são lidos de um checkout limpo, com hash do arquivo e três linhas de contexto por lado.
Arquivos excluídos não são lidos para extrair trechos. Metadados ausentes não excluem casos;
CWE desconhecida resulta em `OUTRO`, e RAG sem mapeamento em `generico`.

Saídas oficiais: [catálogo](../outputs/catalogos/ampliado_v1/catalogo_issues.json),
[exclusões](../outputs/catalogos/ampliado_v1/exclusoes.json) e
[metadados](../outputs/catalogos/ampliado_v1/catalogo_meta.json).
A [especificação](../features/01-catalogo-ampliado/README.md) e o
[relatório de entrega](../features/01-catalogo-ampliado/ENTREGA.md) detalham o contrato e a reprodução.

Esta geração não altera as entradas do orquestrador. O catálogo histórico, seus resultados e
os scripts anteriores foram preservados. Congelamento do perfil ampliado, comparação posterior
R/M e seleção do novo catálogo no pipeline permanecem pendentes.


## 12. Integração do catálogo ampliado — feature 02

A execução ampliada seleciona catálogo, perfil e saída explicitamente. O loader verifica
hashes, schema, IDs, coordenadas e fontes arquivadas. O commit esperado vem do catálogo;
a configuração de ambiente, quando preenchida, deve coincidir.

O perfil local `config/perfis/ampliado_v1/perfil.json` congela as regras remotas exportadas
e as regras locais, incluindo hashes, IDs, exclusões e timeouts. Sua exportação remota foi
obtida após a auditoria e verificada por reprodução do multiconjunto de 78 ocorrências.
A reprodução dos achados não prova que todo o conteúdo das regras é idêntico à versão
histórica não arquivada; fixa o detector utilizado nesta nova etapa.

Antes de criar cliente LLM, o preflight exige reprodução completa, verifica o checkout e
monta prompts. `--somente-preflight` não exige dependências Node, API ou testes funcionais.
Dry-run e tentativas usam worktrees com dependências e referência funcional selecionada
por `--baseline-testes`, preservando a referência histórica.

A comparação ampliada realiza scans globais e pareia ocorrências de arquivos inalterados
por coordenadas. Em arquivos alterados, utiliza blocos de linhas idênticos e únicos nos
dois arquivos, traduzindo o deslocamento. Grupos com anteriores e posteriores não pareados
ficam indeterminados. R/M nulos não geram aceite automático.

Avisos de parsing idênticos já presentes em arquivos não alterados permanecem como
cobertura limitada. Diagnósticos novos, problemas em arquivos alterados, falha operacional
ou timeout tornam as medições afetadas inconclusivas. Findings em arquivos sem cobertura
anterior não são declarados novos comprovados. A confirmação dinâmica continua necessária
para conclusões de segurança.

A retomada exige contrato com commit, hashes de catálogo/metadados/perfil, estratégias,
casos, comparador, templates e referência funcional. O baseline e os artefatos das linhas
concluídas são conferidos por hash. As execuções ampliadas não são misturadas a E01/E02.

TRV mantém indeterminados no denominador como tentativas sem remediação validada; as taxas
auxiliares ampliadas utilizam valores medidos e denominadores explícitos. Os cálculos
históricos ficam preservados. F continua medindo a cobertura atual do servidor, sem
alegar validação integral de frontend.


## 13. RAG simplificado e preparação das quatro estratégias — feature 03

A base documental 1.0 contém dez documentos originais em português, com exemplos genéricos JS/TS e referências específicas a OWASP, CWE, Node.js, Angular e Sequelize. Os documentos não incorporam soluções do alvo ou patches anteriores. O manifesto congela bytes do índice, documentos e corpos. Frontmatter e fontes são excluídos dos prompts; corpos de até 20.000 caracteres não são truncados.

A recuperação percorre `cwe_ids` na ordem registrada (ou extrai IDs da lista histórica `cwe`), seleciona a primeira CWE mapeada, depois usa `categoria_rag` se conhecida e por último `generico`. Não consulta auditoria, desafios ou respostas anteriores. Os mapas e o catálogo das features anteriores permanecem intactos. `categoria_rag` e `rag_categoria_recuperada` são registradas separadamente.

P3 inclui tarefa, código, o mesmo bloco SAST de P1L, corpo recuperado, restrições e formato. P4 acrescenta o roteiro existente após o contexto. Papel, restrições, formato, política de janela e mensagens/hashes P1/P2/P1L foram preservados. A base completa é revalidada em cada uso; indisponibilidade não impede estratégias sem RAG.

Novas execuções utilizam contrato 2.0: componentes textuais e política de contexto são identificados por hash, com demais campos científicos preservados. Execuções RAG incluem manifesto, índice e documentos; alteração impede retomada. Para contrato 1.0 sem RAG, a equivalência exige campos científicos, hashes de roteiro/validação e mensagens/hashes de todos os pares caso/estratégia. O contrato antigo não é migrado nem regravado; evidência incompleta exige nova saída. Não adicionar P3/P4 à saída antiga.

O preflight `AMP_RAG_PREFLIGHT_01` produziu 312 prompts e 156 recuperações P3/P4 para os 78 casos. Todos selecionaram por CWE. Os 21 falsos positivos e 49 casos sem OWASP foram mantidos. Fallback e múltiplas CWEs foram testados com fixtures; não há esses casos no conjunto oficial. Oito diagnósticos preexistentes de parsing foram preservados. Nenhum cliente LLM, patch ou teste funcional foi executado nessa preparação.

Recuperação por categoria não confirma vulnerabilidade nem especificidade da recomendação: CWE-915 seleciona documento amplo que não detalha poluição de protótipo. P3/P4 adicionam SAST e documentação juntos; eventual efeito não deve ser atribuído exclusivamente a RAG. Correções reais, custos, R/F/M e validação específica de frontend pertencem às próximas entregas.

Comandos e hashes estão na [entrega](../features/03-rag-prompts/ENTREGA.md); a [cobertura](../outputs/feature03/cobertura_rag.json) preserva categoria original/recuperada, motivo, CWE e tamanhos por caso.


## 14. Consolidação verificável — feature 04

O consolidado novo usa `criterio` como definição principal de F, exportando sensibilidade para as três definições sobre a mesma cadeia observada. A primeira classificação original de aceite delimita essa cadeia; registros posteriores são conservados como pós-aceite. O comando histórico mantém a cadeia retrospectiva e seus arredondamentos.

TRV inclui tentativas não aplicadas e indeterminadas no denominador da população, sem transformá-las em medições negativas. No ampliado, TRI/TPF/TNINI utilizam denominadores medidos, conforme a política da feature 02; proporções mínimas sobre todas as tentativas são suplementares. TFF usa o mesmo denominador de TPF. Ausência de medição não é falha funcional comprovada. Denominador zero resulta em valor nulo, com motivo.

Casos solicitados vêm do contrato; sem conjunto histórico verificável, reporta-se apenas a taxa por casos observados. P1L, simulações e desenho real são populações separadas. Cache não constitui nova cobrança nem réplica independente. Custos conhecidos e completude são explícitos; durações acumuladas não equivalem ao tempo de parede de workers paralelos.

Os agrupamentos por CWE usam conjunto composto, sem duplicação. Ausência de OWASP e classificação falsa positiva/inconclusiva não excluem tentativas. A seleção sequencial das estratégias impede interpretar taxas brutas como efeito causal.

RRIS é calculada somente de evidência conjunta verificável, com scans globais comparáveis e patches aceitos identificados. Não se somam R ou aceites isolados. Diagnósticos novos, arquivos alterados com parsing limitado, diagnósticos anteriores desaparecidos sem evidência de cobertura e falhas operacionais tornam a comparação indeterminada. Limitação estática idêntica em arquivos inalterados é registrada. Falha funcional conjunta impede chamar o conjunto de remediação validada, mesmo havendo redução estática.

Publicação ocorre em saída nova, com lock, revalidação de fontes e promoção exclusiva. O manifesto registra hashes e políticas, sem timestamp de geração. Os cálculos históricos foram reproduzidos em cópias; as evidências oficiais anteriores não foram regravadas.

A validação encontrou divergência preexistente no YAML remoto do perfil atual. Um snapshot exato do Git, com os hashes do manifesto original, foi arquivado na preparação da feature 04; a divergência permanece registrada. Isso não altera a metodologia nem o detector histórico. Novos scans precisam selecionar um perfil íntegro.

Veja [especificação](../features/04-metricas-consolidacao/README.md) e [entrega](../features/04-metricas-consolidacao/ENTREGA.md).

## Otimização experimental da validação — feature 05

A feature 05 introduz a política opcional `otimizada_v1`. O padrão permanece
`historica_v1`, cache desligado e repetição ampla. A política otimizada executa
compilação e testes relacionados antes da confirmação ampla, mantendo SAST global
mesmo quando a triagem funcional reprova. R/M negativos ou indeterminados não
impedem medir F. Aprovar apenas a triagem não autoriza F positivo.

O mapa revisado associa arquivos alterados a testes de servidor/API; arquivos não
mapeados e componentes compartilhados usam fallback amplo. Esse fallback preserva
a cobertura existente de servidor/API: não passa a cobrir testes Angular ou Cypress.
A classificação F/D e a regra de parada da cadeia permanecem inalteradas.

Novas execuções ampliadas registram contrato 3.0, com política, mapa, implementação,
conjunto D e ambiente efetivo. Contratos 1.0/2.0 continuam legíveis; mudanças
científicas exigem nova execução, sem migração ou sobrescrita dos artefatos antigos.
A reserva do workspace impede execuções concorrentes de processos que usam as novas
entradas do pipeline. Dentro da execução, K controla casos; estratégias do mesmo
caso continuam sequenciais e as etapas de API compartilham o lock de porta.

Cache de SAST e cache funcional são independentes do cache de respostas LLM. Uma
observação só é reutilizada com identidade de conteúdo, ambiente e implementação
compatível, artefatos íntegros e proveniência registrada. R/M são recalculados por
ocorrência mesmo em um hit de scan. Alterações não explicadas em estado local dos
testes impedem a publicação funcional. Reutilizações não são novas réplicas de LLM
nem novas medições independentes de qualidade. Tempos atuais e originais são separados.

A repetição seletiva de API é experimental e fica desligada por padrão. Cobertura
incompleta ou ambígua retorna à repetição ampla. Sua investigação deve comparar
resultados e evidências, pois dependências de ordem podem não aparecer isoladamente.

O benchmark da feature usa patches arquivados, sem gerar correções ou chamar a LLM.
Seus replays ficam fora das populações de remediação e preservam os resultados
históricos. A recomendação de política/K depende das medições e das limitações
registradas na entrega; a simples implementação não demonstra aceleração.


### Resultado da avaliação da feature 05

A matriz de 96 replays dos oito patches preservou R/M e as três definições de F.
K=1 frio ficou praticamente empatado com a política histórica (0,443% de redução
mediana); K=2 frio reduziu 15,970% frente ao otimizado K=1, em três repetições.
A preparação foi medida separadamente. Cache funcional não teve hits no alvo por
mudanças de identidade; cache SAST teve três hits frios/oito quentes por rodada.
Uma diferença de intermitência externa apareceu no K=2 quente. Cache quente e
repetição seletiva têm observação única e permanecem exploratórios.

A política vigente não foi alterada. Recomenda-se avaliar otimizado/K=2/repetição
ampla em novo piloto controlado antes de congelar a campanha. A cobertura continua
sendo a suíte de servidor/API já existente, sem Angular/Cypress. Veja os hashes,
preparações descartadas e limites na [entrega](../features/05-otimizacao-validacao/ENTREGA.md).


### Política relacionada, decisão posterior à feature 05 — 16/10/2026

A entrada `config/execucao.yaml` seleciona `relacionada_v1`: T0, união explícita dos
testes unitários/API dos arquivos alterados e SAST global. Não se exige T3/T4
amplo. F mede a cobertura relacionada declarada, mantendo as três separações F/D
e a parada vigente; não representa regressão global verificada. Mapeamento
insuficiente não aciona suíte ampla e não autoriza F positivo. Antes da LLM,
recusam-se seleções de casos sem mapa revisado; lacunas adicionais introduzidas
pelo patch geram indeterminação funcional, preservando R/M.

A política e seu hash de implementação integram o contrato 3.0. Os contratos e
resultados anteriores não são alterados; a nova política exige outra execução.
A matriz de desempenho da feature 05 continua descrevendo as políticas históricas
medidas, não esta cobertura mais restrita. Testes automatizados verificam seleção,
F/D, SAST mesmo após falha e ausência das chamadas às suítes amplas. Não foram
executados LLM, scan ou testes do alvo para esta alteração. Consulte a
[definição operacional](validacao_relacionada.md).


### Calibração exploratória com referências dos Coding Challenges — 17/10/2026

Foram avaliadas, fora do pipeline LLM, 63 alternativas de 17 desafios em cópias
isoladas dos arquivos completos, usando o perfil congelado. São 13 casos distintos
do catálogo; há alternativas compartilhando casos e fontes. Todos os alertas
originais avaliados foram reproduzidos; F não foi medido e M_fixture não é M global.
Das 17 alternativas marcadas corretas, 12 tiveram R=1/M_fixture=1, quatro alguma
indeterminação e uma manteve o alerta associado. Isso revela limites de pareamento
e de associação entre desafio e regra, sem estabelecer precisão/recall do SAST.

`codefixes/` permanece excluído dos prompts, RAG e escopo operacional. As referências
pedagógicas só foram injetadas em fixtures temporárias para esta auditoria; não
foram aplicadas às worktrees. Os scans brutos e códigos anteriores/posteriores
ficam em saída separada, com hashes e inventário. Nenhum critério de aceite,
comparador, regra ou catálogo foi alterado. Este conjunto foi inspecionado e não
poderá ser apresentado como avaliação independente de um comparador ajustado a ele.
Veja o [relatório e as mudanças recomendadas](auditoria/avaliacao_referencias_codefixes.md).

### Comparação por contexto e revisão das associações — 17/10/2026

Execuções ampliadas novas passam a usar `ocorrencias_contexto_v2`, mantendo a
política de cobertura/parsing da v1. Após blocos únicos de linhas, o comparador
usa blocos de tokens, foco único e chamadas únicas no mesmo escopo com âncora
lexical verificável. Preserva multiplicidade e pareamento um para um; casos sem
evidência suficiente continuam indeterminados. R=0 indica persistência do alerta,
não confirmação de exploração. O contrato identifica o comparador e inclui o
adaptador sintático na implementação; o ambiente identifica suas dependências.

A reanálise offline dos scans arquivados reduziu indeterminações de 28 para 6
entre 63 referências e de 4 para 0 entre oito patches. As 17 referências corretas
tiveram 16 resultados R=1/M_fixture=1 e um R=0/M_fixture=1. F não foi remensurado;
M_fixture não é global. Este conjunto é de calibração observado, sem inferência
de precisão/recall. Os artefatos anteriores não são reclassificados.

Revisões de associações são uma camada documental separada e versionada. Nenhuma
regra, ocorrência, prompt, classificação da auditoria ou critério F/D foi alterado.
Alternativas incorretas que removem alertas reforçam a necessidade de validação
funcional independente. Retomadas com comparador divergente são recusadas; novas
execuções usam outra saída. Veja a [entrega, comandos e evidências](auditoria/comparador_v2.md).


### Cobertura funcional por grupos revisados — feature 06, 17/10/2026

A política optativa `relacionada_v2` usa revisão 1.0, mapa derivado 2.0 e baseline
funcional 2.0. O contrato 4.0 vincula revisão, mapa, D, avaliadores, adaptadores,
ambiente e baseline. As políticas e os contratos anteriores não são migrados; a
configuração padrão é preservada. O preflight verifica prontidão antes de criar
cliente LLM, sem executar testes funcionais.

Depois do patch, a seleção é a união dos comportamentos revisados de todos os
arquivos alterados, sem fallback amplo. F positivo requer compilação dos domínios,
execução dos testes obrigatórios e baseline comparável. Lacuna, timeout, skip
obrigatório ou avaliador alterado impedem aprovação; falha comprovada produz F=0.
As três definições F/D, comparador SAST e parada da cadeia permanecem vigentes.
R/M continuam medidos globalmente, independentemente da avaliação funcional.

Angular usa build development com AOT e saída temporária; Vitest/jsdom executa
arquivos explícitos com JUnit e timeout de 300 segundos por grupo. Não representa
navegador real nem integração completa entre frontend e servidor. Testes adicionais
são materializados exclusivamente e removidos antes do scan; falha de limpeza
interrompe a medição. Arquivos de teste alvo exigem avaliação independente.

O conjunto D novo preserva as 75 entradas anteriores. As 33 asserções Angular
candidatas revisadas observam mocks/estado, sem demonstração suficiente de
exploração: nenhuma foi acrescentada a D. Critérios anteriores permanecem iguais.

A auditoria concluiu 63 revisões adequadas e 15 insuficientes, com 52 casos
preparados e 26 bloqueados pela união por arquivo. A campanha dos 78 permanece
pendente. Baselines compartilhados não são 78 medições independentes. Métricas
acrescentam agrupamento por alcance funcional, sem mudar denominadores; registros
antigos não recebem alcance inventado. Consulte a
[entrega, controles e evidências](../features/06-cobertura-funcional/ENTREGA.md).


### Correção da medição funcional do piloto K=4 — 17/10/2026

A primeira execução de dez casos revelou ausência de builds ignorados pelo Git
em duas worktrees. Falhas de startup foram interpretadas como asserções F em
13 registros. A execução original permanece preservada como evidência do problema,
sem substituição retrospectiva de métricas.

A política `relacionada_v2` passa a exigir artefatos de inicialização e porta
disponível, vinculando os hashes desses artefatos ao ambiente. O adaptador de API
aguarda as pré-condições assíncronas antes de descobrir testes. Falha operacional
de um grupo não fornece reprovação F; sem outra reprovação comprovada, a medição
fica nula. As três definições F/D e o tratamento dos desafios permanecem iguais.

Foi gerado baseline novo, seguido de revalidação isolada dos patches existentes.
A revalidação não gera respostas LLM nem constitui nova amostra independente.
Mudanças de ambiente/implementação impedem retomadas antigas; os YAMLs atuais
referenciam a nova evidência. Veja o
[diagnóstico, comandos e resultados](auditoria/correcao_validacao_piloto10.md).

## Provedor Colab e identidade de inferência

Novas execuções ampliadas podem selecionar Qwen no Colab e usam contrato 5.0. Modelo/revisão/tokenizer/template/quantização/geração são identificados separadamente do endpoint. Preservam-se prompts, critérios R/F/M, denominadores e parada da cadeia. O contador Colab é independente do histórico OpenAI; custos não informados permanecem nulos. Erro operacional interrompe a fila e não é reprovação funcional; resposta truncada não é aplicada. A entrega 07 foi testada offline, sem demonstrar desempenho ou eficácia na GPU. [Preparação e limites](modelo_colab.md).
