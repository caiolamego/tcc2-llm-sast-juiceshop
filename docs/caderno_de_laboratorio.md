# Ambiente de referência

Versões das ferramentas usadas na preparação do ambiente (F0.1), registradas aqui para reprodutibilidade.

| Ferramenta | Versão |
| --- | --- |
| Node.js | v26.7.0 |
| npm | 11.19.0 |
| Python | 3.11.16 |
| Git | 2.50.1 (Apple Git-155) |

---

# Caderno de laboratório

Registro cronológico de decisões técnicas tomadas em tempo de execução, anomalias, desvios do plano documentado no guia e medições. Este arquivo é fonte primária para a seção de Limitações do TCC 2: qualquer coisa que afete a reprodutibilidade do experimento entra aqui, não só é corrigida silenciosamente no código.

Uma entrada por incidente. Não delete entradas antigas — se algo for revertido depois, registre a reversão como nova entrada.

## Formato de cada entrada

```
### AAAA-MM-DD — título curto

**Sintoma:** o que foi observado
**Causa:** diagnóstico
**Correção:** o que foi mudado
**Impacto na reprodutibilidade:** sim/não — se sim, por quê
**Fase do guia:** referência (ex.: F2.2)
```

---

## Entradas

### 2026-09-08 — `npm ci` falha na preparação do alvo (F2.2)

**Sintoma:** `scripts/setup_target.sh` falhava no passo `[4/4]` (instalação de dependências) com erro do `npm ci` exigindo um lockfile existente.

**Causa:** o repositório upstream do OWASP Juice Shop lista `package-lock.json` no próprio `.gitignore` — o lockfile não é versionado no projeto. `npm ci` exige um `package-lock.json` presente e falha sem ele. Não é incompatibilidade de plataforma: acontece em qualquer máquina.

Um segundo erro apareceu ao tentar `npm install` manualmente como workaround: falhou por ter sido executado na raiz do repositório do TCC (onde não há `package.json` de aplicação), e não dentro do worktree do alvo (`workspace/wt-1`).

**Correção:** `scripts/setup_target.sh` alterado de `npm ci --no-audit --no-fund` para `npm install --no-audit --no-fund`. O comando roda dentro da subshell `( cd "$WT" && ... )`, então, executado via script, sempre acontece no diretório correto — o segundo erro só ocorre se o comando for repetido manualmente fora do script.

**Impacto na reprodutibilidade:** sim. Sem lockfile versionado, `npm install` resolve as versões de dependências de acordo com os ranges (`^`, `~`) do `package.json` no momento da execução — o conjunto de versões instalado pode divergir entre execuções feitas em datas diferentes, ou entre as máquinas dos dois integrantes do grupo.

Precisa constar na seção de Limitações do TCC 2 como fonte de não determinismo do **ambiente**, separada e adicional ao não determinismo já discutido da LLM.

**Mitigação possível (não aplicada ainda):** após a primeira instalação bem-sucedida, copiar o `package-lock.json` efetivamente gerado em `workspace/wt-1/package-lock.json` para `config/package-lock.snapshot.json`, versionado no repositório do TCC, como registro exato das versões usadas no experimento. Isso não restaura o comportamento do `npm ci` (ainda seria preciso `npm install` para reinstalar), mas documenta com precisão o que foi usado, para efeito de reprodutibilidade e de citação na monografia.

**Fase do guia:** F2.2.

---

### 2026-09-17 — Testes falham em worktree limpo: fuso horário, rede externa e conflito de porta (F2.4)

**Sintoma:** ao medir os custos de validação (`measure_validation_cost.py`) sobre `workspace/wt-4`, sem nenhuma alteração de código, T3 (`test:server`) reprovou 3 de 333 testes e T4 (`test:api`, rodado via script) reprovou 5 arquivos inteiros logo no início.

**Causa — três problemas distintos, nenhum relacionado ao pipeline ou ao ambiente do grupo:**

1. **T3 — bug de fuso horário no próprio Juice Shop. Confirmado.** As 3 falhas eram todas em `test/server/utils.unit.test.ts`, função `toISO8601`, sempre com o mesmo padrão: valor calculado um dia **antes** do esperado (ex.: `actual: '2025-12-14', expected: '2025-12-15'`). Padrão clássico de data-só-dia parseada como meia-noite UTC e depois lida com getters de fuso local (`getDate()`) — em qualquer fuso negativo (Brasília é UTC-3), o resultado recua um dia. Confirmado rodando `TZ=UTC npm run test:server`: 333/333 passaram, 0 falhas (antes: 330/333, 3 falhas). É bug pré-existente do Juice Shop, exposto apenas em fusos negativos — não afeta quem roda o CI oficial em UTC.

2. **T4, 1 falha residual — dependência de rede externa.** Um teste em `test/api/internet-resources.test.ts` verifica se uma página real do StackOverflow retorna 200; retornou 403, provavelmente bloqueio de requisição automatizada pelo próprio StackOverflow. Falha externa, fora do nosso controle.

3. **T4, as outras 5 falhas de arquivo inteiro — conflito de porta no script, não no Juice Shop.** `measure_validation_cost.py` subia `npm start` na porta 3000 antes de rodar T4, mas `test:api` sobe sua própria instância do servidor internamente via supertest. Confirmado ao rodar `npm run test:api` manualmente, sem nenhum servidor pré-iniciado: 548/555 passaram, sobrando só a falha de rede do item 2.

**Correção:** duas mudanças, de natureza diferente:

- `scripts/measure_validation_cost.py` alterado para não subir servidor antes de T4 — ele passa a rodar no mesmo grupo de T0/T2/T3, sem servidor pré-iniciado. Servidor pré-iniciado fica reservado só para T5 (Cypress), que precisa de uma URL real para o navegador visitar. Resolve o item 3.
- **Decisão do grupo:** padronizar `TZ=UTC` como variável de ambiente fixa em todo comando que roda testes do Juice Shop (T2 a T5), em vez de implementar comparação de baseline no runner de validação. Resolve o item 1 (confirmado: 333/333 com `TZ=UTC`, 0 falhas). Registrar em `config/config.yaml` e nos comandos de `src/pipeline/validation/runner.py` quando F4 for construído.

**Impacto na reprodutibilidade:** sim.

Sobre o item 1 (fuso horário): resolvido pela padronização de `TZ=UTC`. Precisa constar na seção de Metodologia/Limitações do TCC 2 como ajuste de ambiente necessário para reprodutibilidade entre fusos horários diferentes — sem isso, o mesmo pipeline produziria `Fⱼ = 0` para qualquer correção rodada por alguém em fuso negativo (Américas), mesmo sem nenhuma relação com a correção em si.

Sobre o item 2 (rede externa): **`TZ=UTC` não resolve isso.** O grupo decidiu, por ora, não implementar o mecanismo de baseline por conjunto de falhas (comparar testes que já falhavam antes da correção vs. depois) que resolveria também esse caso. Ou seja: testes com dependência de rede externa (como o do StackOverflow) continuam sendo uma fonte de ruído não tratada — se aparecerem de novo durante a execução completa do experimento, vão gerar falsos `Fⱼ = 0`. Fica como risco conhecido e aceito, não como pendência esquecida.

**Correção de acompanhamento (mesmo dia):** a decisão de `TZ=UTC` tinha sido registrada aqui e no guia, mas não tinha sido de fato aplicada em `scripts/measure_validation_cost.py` — o script continuou chamando os comandos sem a variável. Confirmado numa segunda execução em `workspace/wt-1`: T3 falhou de novo com o mesmo erro de fuso horário, e T4 já mostrava só a falha de rede isolada (confirmando que a correção do conflito de porta, essa sim, funcionou). Corrigido adicionando `os.environ["TZ"] = "UTC"` logo após os imports do script, antes de qualquer `subprocess.run`/`Popen` — processos filhos herdam o ambiente do pai, então isso basta para propagar a variável para `npm`, `npx` e `node` sem precisar alterar cada chamada individualmente. **Confirmado numa terceira execução via script** (não mais manual): T0/T2/T3/T5 passaram, T3 fechou em 0 falhas — só T4 manteve a falha de rede já conhecida e aceita. Incidente encerrado.

**Fase do guia:** F2.4 → decisão nova incorporada a D6 e ao escopo de F4.

---

### 2026-09-24 — `--exclude-rule-file` não existe no Semgrep (F3.2)

**Sintoma:** o comando de baseline SAST (F3.2) falhou com `semgrep scan: unknown option --exclude-rule-file. Did you mean -e?`. `semgrep --version` respondeu normalmente (`1.177.0`) na mesma execução — confirmando que a instalação e o venv estavam corretos, o problema era só a flag.

**Causa:** `--exclude-rule-file` nunca existiu em nenhuma versão do Semgrep — era um nome hipotético escrito no guia antes de confirmar contra `semgrep scan --help` (o próprio guia já marcava isso como pendente de confirmação). O Semgrep tem duas flags de nome parecido e propósito diferente: `--exclude-rule VAL` exclui uma **regra** pelo ID, não um arquivo; `--exclude PATTERN` exclui **arquivo/pasta**, sintaxe estilo `.gitignore`, repetível (uma flag por padrão). Também existe um arquivo `.semgrepignore` lido automaticamente, mas ele precisa estar na raiz de cada worktree (projeto git) — duplicaria `config/semgrepignore` em cada `wt-N` criado.

**Correção:** `config/semgrepignore` passa a ser convertido em uma sequência de flags `--exclude`, uma por linha do arquivo, tanto no comando manual de terminal (F3.2) quanto em `src/pipeline/sast/semgrep_client.py` (F3.3) — adicionada a função `ler_exclusoes()` e o parâmetro `exclusoes` em `executar()`, que antes **não lia o arquivo de exclusão em nenhum momento** (bug separado do da flag: mesmo sem o erro de sintaxe, a função Python nunca aplicava filtro nenhum). As duas correções ficaram no guia.

**Impacto na reprodutibilidade:** sim, mas indireto — não é sobre variar entre execuções, é sobre **correção do próprio filtro**. Sem isso, qualquer execução (manual ou via `semgrep_client.py`) escanearia `node_modules/`, `coverage/`, `data/static/codefixes/` etc., contrariando o protocolo de filtragem pré-registrado em D1 e reintroduzindo o risco de contaminação de treinamento que a exclusão de `codefixes/` existe para mitigar.

**Fase do guia:** F3.2 e F3.3.

---

**Adendo 2 (mesmo dia) — arquivos que não deveriam entrar na análise:** o relatório de performance da execução real do baseline apontou dois arquivos "muito lentos" (`very_slow_files`): `logs/access.log.2026-09-17` (5,0s) e `frontend/src/assets/private/three.js` (6,9s). Nenhum dos dois é código-fonte da aplicação: o primeiro é um log de acesso real, gerado quando `npm start` foi testado em F2.3 (artefato de runtime, não deveria nem existir no momento da análise); o segundo é uma biblioteca de terceiros (three.js, gráficos 3D) vendorizada como asset estático, não é lógica própria do Juice Shop. `config/semgrepignore` atualizado com `logs/` e `frontend/src/assets/private/three.js`. O `baseline_raw.json` gerado antes dessa correção deve ser descartado e a análise re-executada — como o catálogo de issues (F3.4) ainda não tinha sido construído a partir dele, não há retrabalho além de rodar o comando de novo.

---

**Adendo (mesmo dia) — `.semgrepignore` embutido do Semgrep:** a execução real do baseline (30 findings, 896 arquivos escaneados) reportou `Files matching .semgrepignore patterns: 1444` — mesmo sem nenhum `.semgrepignore` criado no worktree. O Semgrep aplica uma **lista de exclusão padrão embutida no próprio binário** quando não existe um `.semgrepignore` explícito no projeto (provavelmente cobrindo binários, imagens, lockfiles — não confirmado em detalhe). Isso é adicional aos 173 arquivos excluídos pelos nossos `--exclude` (esses sim, sob controle nosso, vindos de `config/semgrepignore`).

**Impacto na reprodutibilidade:** mesma categoria de risco já registrada na D2 do guia (rulesets do registro não versionados): a lista embutida pode mudar entre versões do Semgrep sem aviso, afetando quais arquivos entram na análise mesmo com `config/semgrepignore` idêntico. Mitigação já em prática: `semgrep --version` (1.177.0) é registrado em toda execução e o JSON bruto é arquivado — permite rastrear se uma mudança futura de versão explica uma diferença no total de arquivos escaneados. Não investigado a fundo (o conteúdo exato da lista embutida não foi listado) — se o `docs/protocolo-experimental.md` ainda não foi escrito, este é o dado a incluir nele antes de abrir `baseline_raw.json` para olhar os findings individualmente (ordem que a D1 exige, para não confundir filtragem metodológica com cherry-picking).

---

### 2026-09-25 — Semgrep migrou a taxonomia de severidade; filtro excluía findings válidos (F3.4)

**Sintoma:** `build_issue_catalog.py` excluiu 2 dos 21 findings (após dedupe) com o motivo `severidade 'MEDIUM' fora de ['ERROR', 'WARNING']`. `MEDIUM` nunca deveria aparecer — a documentação sempre descreveu `extra.severity` como só `ERROR`/`WARNING`/`INFO`.

**Causa:** confirmado contra a documentação oficial do Semgrep — a ferramenta passou a suportar dois esquemas de severidade que **coexistem na mesma execução**: o legado de 3 níveis (`ERROR`/`WARNING`/`INFO`) e o atual de 4 níveis (`CRITICAL`/`HIGH`/`MEDIUM`/`LOW`), com `ERROR = HIGH`, `WARNING = MEDIUM`, `INFO = LOW`. Regras diferentes do mesmo scan (mesmo dentro do mesmo ruleset) podem usar nomenclaturas diferentes dependendo de quando foram escritas/atualizadas no registro. O código de `build_issue_catalog.py` (`SEVERIDADES_ACEITAS = {"ERROR", "WARNING"}`) só reconhecia o esquema legado, então os 2 findings `MEDIUM` — que são exatamente o nível `WARNING` que o protocolo D1 manda manter — foram descartados por engano.

**Correção:** `SEVERIDADES_ACEITAS` em `scripts/build_issue_catalog.py` ampliado para `{"ERROR", "WARNING", "CRITICAL", "HIGH", "MEDIUM"}`, cobrindo os dois esquemas e excluindo apenas o nível mais baixo em qualquer um deles (`INFO`/`LOW`). O passo 3 do protocolo de filtragem em D1 do guia também foi reescrito para descrever essa equivalência explicitamente.

**Impacto na reprodutibilidade:** sim, mesma categoria de risco já registrada na D2 (rulesets do registro não versionados) — só que desta vez não é o *conjunto* de regras que mudou, é a *taxonomia* usada para descrever severidade. Precisa constar nas Limitações do TCC 2: um protocolo de filtragem escrito contra uma única nomenclatura de severidade pode excluir findings válidos silenciosamente se a ferramenta migrar de esquema entre a escrita do protocolo e a execução. Mitigação: aceitar explicitamente ambos os esquemas, não só o observado no momento da escrita.

**Fase do guia:** F3.4 → D1 (passo 3) atualizado.

---

### 2026-09-25 — Expansão da tabela CWE→sigla a partir de dados reais (F3.4)

**Sintoma:** 12 dos 21 findings elegíveis (57%) caíram em `sigla_vuln = "OUTRO"` — a tabela original de D7 só cobria 12 CWEs, escolhidas antes de rodar o baseline real.

**Causa:** a lista de D7 foi escrita a partir do referencial teórico do TCC 1 (vulnerabilidades mais associadas ao OWASP Top 10), não a partir de uma inspeção do código real do Juice Shop. Rodando o baseline de verdade, apareceram 6 CWEs distintas fora da lista original: `CWE-95` (Eval Injection, 1×), `CWE-73` (controle externo de caminho de arquivo, 4×), `CWE-1357` + `CWE-353` (confiança em componente não verificado / falta de checagem de integridade, 3× — mesmos findings, duas CWEs cada), `CWE-829` (inclusão de funcionalidade de fonte não confiável, 2×), `CWE-601` (Open Redirect, 1×), `CWE-548` (exposição de listagem de diretório, 1×).

**Correção:** `config/mapa_cwe_vuln.yaml` expandido. Duas adições são reaproveitamento direto de siglas existentes (`CWE-95→CODEINJ`, mesma família de `CWE-94`; `CWE-73→PATHTRAV`, mesma família de `CWE-22`). Três exigiram sigla nova: `CWE-1357`, `CWE-353` e `CWE-829` agrupadas sob `INTEGRITY` (não existe doc de RAG correspondente ainda entre os 7 previstos em F1.3 — mapeado como `null` em `config/mapa_categoria_rag.yaml` até decidir se cria um 8º documento ou trata como "sem RAG"). `CWE-601→OPENREDIR` e `CWE-548→INFOEXPOSURE`, siglas novas e isoladas. D7 do guia atualizado com a lista completa. Resultado: 0 de 21 caem em `OUTRO` agora.

**Impacto na reprodutibilidade:** não diretamente — é uma decisão de categorização (taxonomia própria do grupo), não uma falha de ferramenta como as entradas anteriores. Mas precisa constar na Metodologia do TCC 2: a tabela CWE→sigla não foi definida a priori e depois só aplicada — foi ampliada durante a análise, a partir dos dados reais. Isso é filtragem/categorização iterativa, não cherry-picking (nenhum finding foi excluído ou incluído por causa da sigla, todos os 21 elegíveis continuam elegíveis independente do nome que recebem), mas o processo de como a tabela cresceu precisa estar documentado, não só o resultado final.

**Fase do guia:** F3.4 → D7 atualizado.

---

### 2026-09-26 — `docs/protocolo-experimental.md` escrito depois de já ter visto resultados (F3.6)

**Sintoma:** ao fechar a F3.6, notado que `docs/protocolo-experimental.md` nunca tinha sido criado, apesar de a D1 do guia instruir escrevê-lo **antes** de olhar qualquer resultado do SAST — e o grupo já tinha visto o total de findings (30), a distribuição por CWE e a proporção caindo em "OUTRO" antes desse ponto.

**Causa:** o guia registrava os critérios de filtragem espalhados nas Decisões D1–D7, mas nunca forçou a consolidação num documento formal antes da primeira execução real — as decisões foram sendo tomadas e aplicadas diretamente no código (`build_issue_catalog.py`), sem o passo intermediário de documentá-las à parte primeiro.

**Correção:** `docs/protocolo-experimental.md` criado, consolidando os passos 1–6 do protocolo de filtragem (D1), as duas tabelas de mapeamento confirmadas (D7) e o achado sobre a taxonomia de severidade (entrada de 2026-09-25). O documento abre com uma nota de transparência explícita: os critérios de filtragem (passos 1–6) não foram alterados em função do que foi observado, mas a tabela de siglas **foi** expandida depois de ver os dados reais — e isso está descrito como processo, não escondido atrás de uma cronologia idealizada.

**Impacto na reprodutibilidade:** não afeta a reprodutibilidade técnica (os critérios em si são os mesmos, só a documentação formal veio depois). Mas é relevante para a seção de Metodologia do TCC 2: declarar a ordem real de escrita é mais defensável numa banca do que apresentar um documento datado como se tivesse vindo antes da primeira execução quando não veio. Se perguntarem "isso foi escrito antes ou depois de ver os resultados?", a resposta honesta já está registrada no próprio documento.

**Fase do guia:** F3.6.

---

### 2026-09-26 — Três problemas no primeiro `relatorio_baseline.md` real (F3.6)

**Sintoma:** rodando `report_baseline.py` pela primeira vez sobre dados reais, três coisas chamaram atenção: (1) a linha "Findings brutos" mostrava 21, o mesmo número de "Elegíveis" — mas o valor bruto real era 30 (visto no terminal durante F3.4: "Findings brutos carregados: 30", "Duplicatas removidas: 9"); (2) a seção "Por severidade" mostrava `WARNING: 10`, `ERROR: 9`, `MEDIUM: 2` como três níveis separados; (3) o "Top 10 arquivos" incluía `.github/workflows/ci.yml`, `.npmrc`, `frontend/.npmrc`.

**Causa:**
1. `build_issue_catalog.py` nunca persistia os números de `findings_brutos` e `duplicatas_removidas` — eles só existiam como `print()` no terminal daquela execução específica. `report_baseline.py` só lê `catalogo_issues.json`, que já é pós-deduplicação (21 entradas), então rotular esse número como "bruto" estava simplesmente errado.
2. `MEDIUM` é o nome atual de `WARNING` no esquema de 4 níveis do Semgrep (achado de 2026-09-25) — o catálogo guarda a string bruta do Semgrep, então o relatório, sem normalização, mostra os dois como categorias distintas.
3. As regras dos rulesets usados (`p/owasp-top-ten` e outros) cobrem múltiplas linguagens, incluindo YAML — o scan pegou arquivos de configuração de CI/CD (`.github/workflows/`) e do npm (`.npmrc`), que nunca foram excluídos em `config/semgrepignore` porque ninguém antecipou que os rulesets escaneariam esse tipo de arquivo.

**Correção:** `build_issue_catalog.py` agora grava `outputs/sast_antes/catalogo_meta.json` com `findings_brutos`, `duplicatas_removidas`, `total_apos_dedup`, `elegiveis`, `excluidos` — números que antes só existiam de forma efêmera no terminal. Também passou a gravar `severidade_normalizada` (`ALTA`/`MEDIA`) em cada entrada. `report_baseline.py` atualizado para ler o arquivo de metadados (com fallback gracioso se não existir, avisando que o número bruto está indisponível), reportar severidade bruta E normalizada lado a lado, e sinalizar automaticamente findings fora de `.github/`/`.npmrc` numa seção própria, em vez de exigir uma consulta manual toda vez.

O item 3 (escopo) ainda está em aberto — aguardando a contagem exata de quantos dos 21 elegíveis caem fora do código de aplicação antes de decidir se `.github/` e `.npmrc` entram em `config/semgrepignore`.

**Impacto na reprodutibilidade:** sim, para os itens 1 e 2 — sem os metadados persistidos, o número bruto de findings (30) ficaria irrecuperável em qualquer reexecução futura do relatório sem os logs originais do terminal salvos à parte. Precisa constar nas Limitações do TCC 2 como lição sobre persistir dados de auditoria em arquivo, não em saída de console.

**Fase do guia:** F3.6.

---

### 2026-09-26 — `.github/` e `.npmrc` excluídos do escopo do SAST (F3.6)

**Sintoma:** confirmado por contagem exata: 9 dos 21 findings elegíveis (43%) da execução de referência estavam em `.github/workflows/*.yml` (6 arquivos) ou `.npmrc`/`frontend/.npmrc` (2 arquivos).

**Causa:** os rulesets do Semgrep usados (`p/javascript`, `p/typescript`, `p/nodejs`, `p/expressjs`, `p/owasp-top-ten`) cobrem múltiplas linguagens incidentalmente, incluindo YAML — confirmado no relatório da própria F3.2 ("Language: yaml, Rules: 24, Files: 45"). Ninguém antecipou, ao montar `config/semgrepignore` originalmente, que o scan tocaria configuração de CI/CD ou do gerenciador de pacotes — o objeto de estudo sempre foi código-fonte da aplicação.

**Correção:** `config/semgrepignore` e o comando `--exclude` de F3.2 atualizados com `.github/` e `.npmrc`. `docs/protocolo-experimental.md` atualizado (Seção 3, item 1), com a tabela de resultados marcada como desatualizada até a re-execução.

**Decisão de escopo, não só filtro técnico:** esta exclusão é a mesma fronteira já estabelecida no Adendo M1, onde o grupo decidiu que vulnerabilidades de dependências/supply chain (A06:2021 / A03:2025) ficam fora do escopo por "fugir ao fenômeno investigado" (correção de vulnerabilidades no código-fonte da aplicação, validada por testes automatizados que exercitam a aplicação em execução). CI/CD e configuração de pacote são a mesma categoria de risco — nenhum dos dois é testável pela suíte do Juice Shop, que nunca dispara nem valida execuções reais do GitHub Actions. Vale uma frase na Metodologia citando essa consistência entre as duas decisões, tomadas em momentos diferentes pelo mesmo motivo.

**Impacto na reprodutibilidade:** sim — muda a composição do catálogo. F3.2 a F3.6 precisam ser reexecutados; os números da execução anterior (30 brutos, 21 elegíveis) ficam obsoletos assim que a nova rodada terminar.

**Confirmação (mesmo dia, após re-execução completa):** primeira tentativa de re-execução rodou só `build_issue_catalog.py` em diante, reaproveitando o `baseline_raw.json` antigo (esse script nunca chama o Semgrep de novo por design) — resultado idêntico ao anterior, porque a exclusão nunca chegou a valer. Corrigido rodando o comando `semgrep` completo de novo, com as duas flags novas. Resultado final: 15 findings brutos (antes: 30), 3 duplicatas, 12 elegíveis, 0 excluídos, 0 fora do código de aplicação, 5 de 12 com marcador. Reconciliação: dos 30 brutos originais, 15 eram código de aplicação (idênticos aos 15 finais) e 15 eram `.github/`/`.npmrc` — destes, só 9 sobreviviam à deduplicação antes (6 eram duplicatas internas do mesmo arquivo de workflow). As siglas `CMDI` e `INTEGRITY` desapareceram por completo do catálogo final — 100% das ocorrências dessas duas categorias estavam em configuração de CI/CD, nenhuma na aplicação. `docs/protocolo-experimental.md` atualizado com os números finais.

**Fase do guia:** F3.1, F3.2, F3.6 → protocolo experimental atualizado.

---

### 2026-10-07 — Correção do hash do commit fixado do alvo

- Observado: o protocolo e o CLAUDE.md citavam o commit 8ff89794…, mas o runner da F4 registrou f915bddd… em commit_alvo.
- Verificado: o espelho workspace/juice-shop.git não contém o objeto 8ff89794 (cat-file: could not get object info). O commit f915bddd8 é "Bump to v20.1.1", o commit de lançamento da versão. JUICESHOP_COMMIT no .env já estava correto.
- Causa: hash errado transcrito na documentação (sem efeito sobre as execuções).
- Ação: documentação corrigida. Todas as execuções (baseline SAST, custos de validação, cenários da F4) rodaram em f915bddd.
- Pendência: catalogo_meta.json e os JSON de custo não registram o commit do alvo.

---

### 2026-10-07 — Semgrep sem login devolve "requires login" no fingerprint e no código (F3, descoberto na F5)

**Sintoma:** as 12 issues do `catalogo_issues.json` tinham a mesma `assinatura` (`fp:requires login`) e o campo `trecho` igual a `requires login`.

**Causa:** sem autenticação no Semgrep, `extra.fingerprint` e `extra.lines` vêm preenchidos com o texto literal `requires login` em todos os resultados (conferido em `outputs/sast_antes/baseline_raw.json`). `semgrep_client.assinatura()` usava o fingerprint sempre que ele não estava vazio, e o catálogo copiava `extra.lines` como trecho.

**Efeito:** (1) critério R: comparar alertas antes/depois por assinatura confundiria os 12 findings entre si; um alerta qualquer restante no arquivo faria todas as correções parecerem não resolvidas, ou o inverso. (2) Trecho de código: o catálogo não tinha o campo exigido pela Seção 3.5 do TCC 1. O prompt não foi afetado, porque o builder da F5 lê o código do worktree.

**Correção (decisão do grupo):** `assinatura = sha256(check_id + "|" + caminho_relativo)`, que não depende de fingerprint nem do código. `requires login` passa a ser tratado como campo ausente em `_parse`. O trecho é lido do arquivo no worktree (`start.line`–`end.line`, 3 linhas de folga de cada lado), com `trecho_linha_inicio`/`trecho_linha_fim`. Catálogo regenerado a partir do `baseline_raw.json` existente, sem rodar o Semgrep de novo: assinaturas distintas passaram de 1 para 12. Os demais campos (caso_id, check_id, arquivo, sigla, OWASP, marcador) ficaram idênticos e o relatório do baseline não mudou. `catalogo_meta.json` passou a registrar `commit_alvo` e `semgrep_versao`.

**Impacto na reprodutibilidade:** sim. Muda o identificador de comparação antes/depois. Limitação a registrar: com a assinatura por (regra, arquivo), se a mesma regra continuar disparando em outro ponto do mesmo arquivo depois da correção, o alerta conta como não removido (R=0). É coerente com a deduplicação por (check_id, path) do protocolo, mas é conservador.

**Fase do guia:** F3.2, F3.4 (D6); afeta F6/F7 (critério R).

---

### 2026-10-07 — Teste do StackOverflow com 403 permanente; T4 com linha de base (F4/F5)

**Sintoma:** ao incluir o T4 (`test:api`) no runner, o cenário 1 da F4.3 (sem alteração) passou a falhar sempre: 548 de 555 testes passam, 6 são pulados, 1 falha: `test/api/internet-resources.test.ts :: Required Internet resource > StackOverflow question "Less verbose access logs using expressjs/morgan" ...`, com `403 !== 200`.

**Causa:** o teste busca a página real do StackOverflow, que agora responde 403 a requisições automatizadas em todas as tentativas. Antes registrado como falha intermitente ("falha às vezes"); hoje é permanente. Com o T4 bloqueante, nenhuma correção conseguiria F=1.

**Correção (decisão do grupo, opção 2):** linha de base de referência. `scripts/baseline_testes.py` roda T3 e T4 num worktree sem alteração e grava `outputs/baseline_testes.json` (commit do alvo, data, versão do Node, nome de cada teste falho). No runner, cada tier de teste passa quando o conjunto de testes falhos está contido no da linha de base; cada validação registra `testes_falhos_novos`. Nenhum teste é pulado por nome. Os nomes vêm do reporter JUnit do `node --test`, chamado com os mesmos argumentos dos scripts `test:server`/`test:api` do `package.json` (o `npm run ... --` colocaria as flags depois do glob). O runner confere que a linha de base foi gerada no mesmo commit do worktree.

**Achado no mesmo dia:** `test/api/erasure-request.test.ts :: ... POST erasure request does not actually delete the user` falhou 1 vez em 8 execuções do T4 sem alteração (`socket hang up`, ECONNRESET). Por não estar na linha de base, essa falha derrubou o cenário 1 numa rodada. A linha de base de uma execução só não captura testes intermitentes. **Em aberto para o grupo:** gerar a linha de base com N execuções (união das falhas), ou repetir uma vez o tier quando só aparecem falhas novas.

**Impacto na reprodutibilidade:** sim. F passa a depender de `outputs/baseline_testes.json`, que deve ser versionado junto com os resultados e regenerado se o commit do alvo, o Node ou a rede mudarem.

**Fase do guia:** F4.2, F4.3 (D5).

---

### 2026-10-07 — Porta fixa 43210 em `chat.test.ts` limita o T4 em paralelo (F4/F5)

**Sintoma:** investigação de porta para rodar o T4 em vários worktrees ao mesmo tempo.

**Causa:** o `test:api` não sobe servidor numa porta: cada arquivo cria o app em memória (supertest, SQLite `:memory:`). Mas importar `server.ts` dispara `validatePreconditions`, que verifica se `process.env.PORT ?? 3000` está livre e dá `process.exit(1)` se não estiver (`lib/startup/validatePreconditions.ts:66`). Isso resolve com `PORT` por worktree (o runner usa `3100 + N` para `wt-N`). O limite que sobra: `test/api/chat.test.ts:14` abre um servidor falso de LLM na porta fixa `43210`, sem variável de ambiente. Dois worktrees rodando T4 ao mesmo tempo podem colidir.

**Correção:** nenhuma no alvo (não alteramos o Juice Shop). Opções para a F6: rodar o T4 em série (um worktree por vez, com lock), mantendo T0–T3 em paralelo; ou aceitar o risco e registrar. Paralelismo do T4 ainda não testado.

**Impacto na reprodutibilidade:** potencial. Execução paralela do T4 pode gerar falhas espúrias de porta ocupada.

**Fase do guia:** F4.2 (D4); afeta F6.

---

### 2026-10-07 — Edições múltiplas no mesmo arquivo: bug no applier do guia (F5.5)

**Sintoma:** encontrado na leitura do código de referência da F5.5, antes de rodar.

**Causa:** o `aplicar()` do guia lê o arquivo do disco a cada edição e guarda `(alvo, conteudo_novo)` numa lista. Com duas edições no mesmo arquivo, a segunda parte do conteúdo original e, na escrita, sobrescreve a primeira: só a última edição sobrevive, e o patch fica parcialmente aplicado sem nenhum aviso.

**Correção:** `src/pipeline/patching/applier.py` acumula o conteúdo em memória por arquivo (dicionário), aplicando cada edição sobre o resultado da anterior, e só escreve depois de validar todas (atomicidade preservada). Testado: duas edições no mesmo arquivo aplicadas juntas; segunda edição inválida deixa o arquivo intacto.

**Impacto na reprodutibilidade:** não (corrigido antes de qualquer execução real). Sem a correção, a TAP e o F seriam afetados para respostas com mais de uma edição por arquivo.

**Fase do guia:** F5.5 (D3). O trecho de código do guia deve ser atualizado.

---

### 2026-10-07 — Reexecução com interseção para testes intermitentes (F4/F5)

**Sintoma:** `test/api/erasure-request.test.ts` (`POST erasure request does not actually delete the user`) falhou 1 vez em 8 execuções do T4 sem alteração (`socket hang up`) e, por não estar na linha de base, reprovou o cenário 1 numa rodada.

**Causa:** teste intermitente do próprio Juice Shop. Uma linha de base de uma execução só não o captura.

**Correção (decisão do grupo, protocolo 7.2):** quando uma camada acusa testes falhos novos, `runner._avaliar` a executa uma segunda vez; contam contra o F só os testes novos que falharam **nas duas** rodadas (interseção). Cada camada e cada validação registram `reexecucoes` e `testes_falhos_intermitentes` (diferença simétrica: falharam em só uma rodada); a camada guarda também `testes_falhos_reexecucao` e `saida_reexecucao`. Se a segunda rodada não produzir relatório confiável (timeout, erro sem relatório), vale a primeira (conservador). A linha de base não foi ampliada.

Conferido por simulação das duas rodadas (sem rodar a suíte):

| Caso simulado | 1ª rodada | 2ª rodada | Resultado |
|---|---|---|---|
| Intermitente | {A} | {} | passa, `so_falhas_intermitentes`, intermitentes = {A} |
| Real | {A} | {A} | reprova, novos = {A} |
| Misto | {A, B} | {A, C} | reprova, novos = {A}, intermitentes = {B, C} |

Primeiro caso real: sondagem B de JS003 (`reexecucoes = 1`), em que a falha de `keyServer.unit.test.ts` se repetiu e contou.

**Impacto na reprodutibilidade:** sim, define o F. Custo extra só quando há falha nova (~12 s no T4).

**Fase do guia:** F4.2 (D5).

---

### 2026-10-07 — EXP01 × EXP02: restrição de mudança mínima e profundidade da correção (F5)

**Sintoma:** na EXP01 (sem a restrição explícita), a correção de JS003 reprovou no T4 por reescrever a mensagem de erro verificada por `test/api/file-serving.test.ts`. Na EXP02 (com a restrição "Não altere mensagens de erro, textos visíveis ao usuário, nomes de identificadores nem assinaturas de funções existentes"), passou em T0, T2, T3 e T4 com +1/−1 linha.

**Observação relevante:** a correção aceita (bloqueio de `..` e `/`) é defensivamente mais fraca que a reprovada, que também verificava se o caminho resolvido permanece dentro de `encryptionkeys/` (`startsWith`). A restrição de mudança mínima elevou a preservação funcional e reduziu a profundidade da correção. Sondagem A (mesmo dia, sem LLM): **o alerta do Semgrep persiste nas duas** (`R = 0`), porque a regra `express-res-sendfile` é `taint` sem saneadores e não considera validações condicionais (protocolo 7.3).

**Impacto:** material para a discussão sobre engenharia de prompt; os dois diffs ficam arquivados (`outputs/tentativas/JS003_A06_PATHTRAV_P1_EXP01_*` e `_EXP02_*`). A primeira tentativa foi renomeada de `E01` para `EXP01` (`git mv`), para deixar `E01` livre para a execução oficial; a citação da Seção 10 do protocolo foi atualizada.

**Custos:** EXP01 640+548 tokens, US$ 0,00113; EXP02 665+387 tokens, US$ 0,00089; mesmo `system_fingerprint` `fp_adba1d049a`.

**Fase do guia:** F5.3.

---

### 2026-10-07 — Oráculo R depende do modo da regra; sondagens A e B em `sendFile` (F5/F6)

**Sintoma:** hipótese inicial de separar os achados por regras `audit` × `vuln`. `metadata.subcategory` vale `vuln` nos 12 elegíveis, mas 9 têm `.audit.` no `check_id`: os critérios discordam.

**Causa:** nenhum dos dois descreve como a regra decide. Lido no código-fonte das 7 regras (`semgrep/semgrep-rules`, `develop`, commit `a84ff9cc`): 1 é `search` (JS012), 2 são `taint` com saneadores (`parseInt`, `.hash`: JS005, JS009) e 9 são `taint` sem saneadores.

**Correção:** classificação em três faixas (protocolo 7.3). Definições versionadas em `config/semgrep-rules-referencia/` com README (cópia de referência, possivelmente divergente do registro). Catálogo com `subcategoria_regra`, `audit_no_check_id`, `modo_regra` e `saneadores_regra`. Sondagens sem LLM, arquivadas em `outputs/sondagens/`:
- A: patches EXP01 e EXP02 de JS003 → alerta persiste nos dois (`R = 0`).
- B: correção **escrita à mão** (`res.sendFile(file, { root: ... })`, mantendo validação e mensagem) → alerta some (`R = 1`) em JS002, JS003, JS004 e JS007, sem alertas novos. JS004 e JS007 passam em toda a validação. JS002 e JS003 reprovam no T2, porque os testes unitários conferem por mock o caminho completo passado ao `sendFile` (8 testes no JS002, 5 deles de desafio). O T4, rodado à parte para diagnóstico, passa nos dois.

**Impacto na reprodutibilidade:** não muda a TRV, muda a análise (resultados também por faixa). Mostra um conflito concreto entre R e F: a forma que zera o alerta quebra testes acoplados à implementação. As correções escritas à mão não entram em nenhuma métrica.

**Fase do guia:** F3.4 (D1, D6), F7.

---

### 2026-10-07 — `config/semgrepignore` sem `logs/` e `three.js` (F3.2, descoberto na F6)

**Sintoma:** ao preparar a varredura da sessão para a F6, `config/semgrepignore` não continha `logs/` nem `frontend/src/assets/private/three.js`, que estão no comando da F3.2 do guia e na Seção 3 do protocolo.

**Causa:** as duas exclusões foram acrescentadas ao comando manual do baseline, mas não ao arquivo que o código lê.

**Correção:** as duas linhas foram acrescentadas ao arquivo. O baseline de setembro, rodado com o comando do guia, não foi afetado.

**Impacto na reprodutibilidade:** sim, para varreduras feitas pelo código. Sem a correção, a varredura da F6 sairia com contagens diferentes das do baseline.

**Fase do guia:** F3.2 (D1).

---

### 2026-10-07 — F6: orquestração, R contra a varredura da sessão, P2 com roteiro em rascunho

**Sintoma:** implementação da F6 (`src/pipeline/run_pipeline.py`).

**Causa / decisões aplicadas:**
- **R contra a varredura da sessão (decisão do grupo):** os rulesets do registro não são versionados, então o "antes" do R é a varredura do worktree limpo feita no início de cada execução (`outputs/sast_antes/<EXECUCAO>_baseline_raw.json`). Numa retomada da mesma execução, essa varredura é reaproveitada. O baseline de setembro continua sendo a origem do catálogo. As duas são comparadas a cada sessão (`<EXECUCAO>_comparacao_baseline.json`); caso do catálogo sem o alerta na sessão é pulado e registrado.
- **SAST depois:** só os arquivos tocados (o do alerta e os editados), porque a análise do Semgrep é por arquivo. R = assinatura do caso ausente depois. M = nenhuma assinatura elegível pelo filtro do protocolo (Seção 3, passos 2–4, agora em `src/pipeline/sast/filtro.py`, compartilhado com o catálogo) que não existisse antes nesses arquivos. Cada linha do `execucoes.jsonl` grava a saída completa do SAST depois (`sast_depois`, todos os achados normalizados) e o caminho do JSON bruto (`sast_depois_raw`), além de `ocorrencias_alvo` (antes/depois) e `faixa_regra` (protocolo 7.3).
- **Paralelismo:** um caso por worktree (K workers), estratégias em sequência, parando na primeira com R·F·M = 1. T4 serializado por lock entre worktrees (porta 43210); a reexecução da Seção 7.2 roda dentro do lock. Orçamento: conferir, chamar e registrar sob o mesmo lock (sem isso, até K−1 chamadas passariam do limite).
- **Checagem de ambiente:** no início da sessão, a validação roda em cada worktree sem alteração; se algum reprovar, a sessão aborta (cenário 1 da F4.3).
- **Retomada:** lê o `execucoes.jsonl`, pula tentativas registradas e casos já aceitos. Erro inesperado interrompe só o caso, sem gravar linha (a retomada refaz; a resposta da LLM vem do cache).
- **P2:** implementado como P1 + roteiro em etapas, sem alerta SAST (tabela da F5.3; fatorial 2×2 removido no cronograma). O texto do roteiro do TCC 1 não estava disponível (repositório da PoC não encontrado entre os públicos), então `config/prompts/roteiro_raciocinio_guiado.md` contém um **rascunho** (`STATUS: RASCUNHO`), com passos espelhando os seis campos da resposta. Com rascunho, P2 roda só em `--dry-run`; chamada real exige `STATUS: APROVADO`. P1 ficou idêntico byte a byte (hash igual ao da EXP02).
- **P3/P4:** falham na largada com mensagem clara enquanto `knowledge_base/_index.yaml` não existir.

**Critério de conclusão (dry-run completo, `DRY02`):** 12 casos × P1, P2, K=4, 24 tentativas em 617 s, 0 erros. Varredura da sessão igual à de setembro (15 × 15 achados brutos, 12 assinaturas, Semgrep 1.177.0). Todas `rejeitada:R0F1M1`, como esperado de uma resposta falsa que só acrescenta um comentário. Checagem de ambiente: os 4 worktrees passaram. A reexecução da Seção 7.2 atuou 2 vezes e evitou 2 F=0 espúrios: em JS006/P1, `internet-resources › Comment on "Top 10 Fruits…"` e `memory.test.ts › Should not crash … CVE-2022-24434`; em JS007/P2, o mesmo teste de `internet-resources`. São mais dois testes intermitentes além do `erasure-request`, e ambos se resolveram na segunda rodada. Caminho de aceite conferido à parte (`DRYACEITE`, correção escrita à mão em JS004): aceita em P1, P2 não executado.

**Impacto na reprodutibilidade:** sim. Define como R é medido e onde ficam os artefatos (`outputs/prompts/`, `respostas_llm/`, `patches/`, `codigos_corrigidos/`, `sast_depois/`, `testes/`, `resultados_consolidados/`); o dry-run usa a mesma estrutura em `outputs/dry_run/`.

**Fase do guia:** F6.

---

### 2026-10-08 — Roteiro do P2 substituído pelo texto do TCC 1 (Seção 4.2.4)

**Sintoma:** o roteiro em `config/prompts/roteiro_raciocinio_guiado.md` era um rascunho (`STATUS: RASCUNHO`, seis passos espelhando os campos da resposta), escrito sem acesso ao TCC 1.

**Causa:** o texto original não estava no repositório.

**Correção:** o grupo substituiu o arquivo pelo texto da Seção 4.2.4 do TCC 1 (cinco etapas: identificar, explicar a causa, descrever o impacto de segurança, propor a correção, justificar tecnicamente), com `STATUS: APROVADO`, a tabela de correspondência entre as etapas e os seis campos da resposta, e a nota de congelamento (2026-10-08). O arquivo novo é um documento, então `builder.carregar_roteiro()` passou a extrair **só** o bloco cercado por ``` da seção "Bloco a ser inserido no prompt", e falha se ela não existir. Sem essa mudança, as 65 linhas do documento iriam para o prompt. Conferido: o bloco extraído é idêntico ao do arquivo (sha256 `6ac34725…`), o P2 é exatamente P1 + esse bloco entre o código e as restrições, e o P1 continua idêntico (mesmo hash da EXP02). Com `STATUS: APROVADO`, o P2 deixou de estar restrito ao dry-run.

**Impacto na reprodutibilidade:** sim. Define o conteúdo do P2 na E01; o `roteiro_sha256` vai em cada linha do `execucoes.jsonl`.

**Fase do guia:** F5.3.

---

### 2026-10-08 — Primeira tentativa da E01 abortada: T4 travado no wt-4

**Sintoma:** na checagem de ambiente da primeira sessão da E01 (20:36 UTC), o T4 do `wt-4` (sem alteração) ficou parado em `test/api/password.test.ts` até o timeout de 300 s. O `wt-4` reprovou e a sessão abortou **antes de qualquer chamada à LLM** (contador de orçamento inalterado: 2 chamadas, US$ 0,002). O `wt-3` levou 346 s, mas passou: ficou esperando o lock do T4, preso pelo `wt-4`.

**Causa:** não identificada. O teste não acessa rede (app em memória). Rodado logo depois, duas vezes, o T4 do `wt-4` passou em 11 s cada vez. Foi um travamento pontual, não defeito do worktree.

**Correção:** nenhuma no critério. A sessão foi reiniciada com K=4. O orquestrador passou a gravar a sessão em `<EXECUCAO>_sessoes.json` também quando aborta (antes, a checagem abortada não deixava registro) e a registrar o motivo de cada camada na checagem.

**Em aberto para o grupo:** a reexecução da Seção 7.2 vale só para testes falhos novos. Um travamento como este durante uma tentativa real gera F=0 por `timeout` sem reexecução. Opção: estender a reexecução a `timeout` no T4.

**Impacto na reprodutibilidade:** potencial. Timeout no T4 pode produzir F=0 espúrio.

**Fase do guia:** F4.2, F6.

---

### 2026-10-08 — Execução E01 (P1, P2; 12 casos): resultado e achados

**Sintoma:** E01 concluída (sessão 20:42:54–20:51:48 UTC, 450,7 s de processamento após a checagem de ambiente). 24 tentativas, 0 erros, **0 correções aceitas** (TRV = 0). Métricas preliminares (antes da F7) em `outputs/resultados_consolidados/E01_metricas_preliminares.json`. 19 chamadas reais (US$ 0,02498; 27.017 + 9.220 tokens) e 5 respostas do cache. `system_fingerprint` único: `fp_adba1d049a`. Varredura da sessão igual à de setembro (15 × 15). Checagem de ambiente: 4 worktrees OK; no `wt-2`, `feedback.test.ts › DELETE existing feedback` foi intermitente e se resolveu na reexecução.

**Achados (para a análise; nenhum critério foi alterado):**
1. **Prompts idênticos entre casos.** JS005/JS006 (`routes/login.ts`, linha 34) e JS009/JS010 (`routes/search.ts`, linha 23) são regras diferentes no mesmo ponto do mesmo arquivo. Como P1 e P2 não recebem o alerta SAST, o prompt é o mesmo, e a segunda chamada veio do cache, com patch idêntico. Na prática, 10 problemas distintos para a LLM, não 12.
2. **JS003/P1 da E01 é a resposta da EXP02:** mesmo prompt, modelo e seed; veio do cache. Determinismo esperado (D8), mas a E01 de JS003/P1 não é uma chamada independente.
3. **Sem o alerta, a LLM corrigiu outra vulnerabilidade.** Em JS001 (segredo JWT fixo em `lib/insecurity.ts`), P1 e P2 alteraram a linha do allowlist de redirecionamento (`vuln-line redirectChallenge`) no mesmo arquivo. R = 0 e reprovação no T3 por um teste de desafio. É a variável de confusão do Adendo M4 aparecendo nos dados.
4. **Testes de desafio (Risco 2, conjunto D) derrubam correções que parecem corretas.** JS005/JS006 (P1 e P2): consulta parametrizada com `replacements`, R = 1, M = 1, e reprovação no T4 só pelos 5 testes de `login.test.ts` que executam ataques de SQL injection e esperam que funcionem. JS011/P1: R = 1, reprovação só em `user-profile.test.ts › … renders evaluated SSTI payload …`. JS001: `redirect.unit.test.ts › tricking the allowlist should solve "redirectChallenge"`. A classificação F × D é feita na análise (protocolo 7.1), não no pipeline.
5. **Falhas de compilação (T0):** JS009/JS010 (P1 e P2: `Property 'QueryTypes' does not exist on type 'Sequelize'`) e JS008/P2 (`Property 'some' does not exist on type 'Set<string>'`).
6. **Faixa 3 (`sendFile`, JS002–JS004, JS007):** todas com F = 1 e R = 0, como a sondagem A antecipou (validação condicional não remove o alerta).
7. **Patch não aplicável:** JS012/P1 e JS011/P2 (`ancora_nao_encontrada`); TAP = 22/24.

**Correção (código):** o custo acumulado da sessão no log somava respostas do cache (US$ 0,03075 no log; real US$ 0,02498); corrigido em `run_pipeline.py`. A primeira sessão abortada (entrada anterior) não ficou em `E01_sessoes.json`, porque o registro de sessão abortada foi acrescentado depois dela.

**Impacto na reprodutibilidade:** os achados 1 e 2 afetam a independência entre casos e devem constar da Metodologia. Os achados 3 e 4 são resultado.

**Fase do guia:** F6, F7, F8.

---

### 2026-10-08 — Decisões antes da E02: E01 preliminar, timeout, Seção 10 e condição P1L

**Sintoma:** a E01 mostrou falhas em testes de desafio sem separação F/D implementada, risco de F = 0 por travamento, um parágrafo errado na Seção 10 e a confusão do Adendo M4 nos dados.

**Causa / decisões do grupo:**
- **E01 arquivada como execução preliminar**, anterior à separação F/D. Nada dela é apagado. A execução oficial será a E02.
- **Timeout também dispara reexecução** (protocolo 7.2, extensão): uma vez, em T0, T2, T3 e T4. Sem relatório da primeira rodada não há interseção; vale a segunda. Campo `timeout_na_primeira_rodada`. Conferido por simulação: timeout→passa (passa), timeout→timeout (reprova, `timeout`), timeout→falha A (reprova, A conta).
- **Seção 10 reescrita:** a lição de EXP01 × EXP02 é a troca entre profundidade da correção e preservação funcional (as duas têm R = 0), e não divergência entre R e F. A divergência entre R e F passa a ser ilustrada por JS005, JS006 e JS011 da E01. A nota de correção provisória foi removida.
- **Condição de diagnóstico P1L** (protocolo, Seção 12): P1 + bloco com arquivo, linha, regra, CWE e mensagem do alerta. Não é estratégia do desenho; mede o efeito de o prompt não dizer o que corrigir (confusão prevista no Adendo M4). Roda sempre, fora da cadeia (`--diagnosticos P1L`), com `condicao = diagnostico` em cada linha. Conferido: P1L = P1 + bloco; P1 inalterado (hash da EXP02); com o P1L, JS005 × JS006 e JS009 × JS010 passam a ter prompts distintos; em dry-run, com P1 aceito, o P2 foi pulado e o P1L rodou.

**Correção:** `runner.py`, `builder.py`, `run_pipeline.py`; protocolo 7.2, 10 e 12.

**Impacto na reprodutibilidade:** sim. Muda o critério F (timeout) e acrescenta uma condição às execuções a partir da E02.

**Fase do guia:** F4.2, F5.3, F6.

---

### 2026-10-09 — Separação F/D: critérios, lista a priori e duas definições

**Sintoma:** o marcador de desafio (asserção `challenges.<id>.solved, true`), proposto em 2026-10-08, não captura os testes de exploit da API (SQL injection em `login.test.ts`, SSTI em `user-profile.test.ts`), que afirmam que o ataque funciona sem citar desafio.

**Causa:** o marcador operacionaliza só uma parte da definição da Seção 7.1.

**Correção (decisão do grupo, protocolo Seção 13):**
1. Critérios (a), (b), (c) escritos **antes** de classificar qualquer teste: `docs/criterios_conjunto_d.md`.
2. Varredura de `test/api/` e `test/server/` inteiros (863 blocos `it(...)`): 75 testes em D (36 por (a), 29 por (b), 10 por (c)) e 35 examinados e mantidos em F, 12 deles sinalizados para decisão do grupo. Lista em `docs/conjunto_d.md` e `config/conjunto_d.json`, gerados por `scripts/gerar_conjunto_d.py`. Todas as 110 linhas citadas (do `it` e da asserção) foram conferidas contra o arquivo.
3. Duas classificações em cada validação: `d_marcador` (só (a)) e `d_criterio` (lista completa), além de `F_sem_separacao` (regra da E01). Escada só para em falha fora de `d_criterio`; cadeia só para em aceite sem separação. Métricas e TCD nas três versões (`scripts/metricas_execucao.py`). Conferido por simulação de seis cenários de escada e por dry-run com a consulta parametrizada de JS005 escrita à mão (F sem/marcador/critério = 0/0/1).

**Erro encontrado e corrigido no caminho:** a primeira versão da extração contava a linha em branco anterior ao `it(...)`, deslocando a linha do teste em −1; corrigido e conferido linha a linha.

**Reclassificação a posteriori da E01 (só para comparação):** sob `d_criterio`, JS005, JS006 e JS011 seriam aceitos (TRV por tentativa 0 → 0,143; 3/12 casos); sob `d_marcador`, nada muda. JS001 fica indeterminado: a escada da E01 parou no T3 (teste (a)) e o T4 não rodou; o R dele é 0 de qualquer forma.

**Achado no mesmo dia:** segundo travamento do T4. No dry-run de teste da separação (JS005/P2), a primeira rodada terminou em ~11 s, com os 5 testes (b), e a reexecução da interseção travou até 300 s. Pela regra, vale a primeira rodada (conservador), e a classificação saiu correta. A saída capturada não permite identificar o arquivo travado.

**Impacto na reprodutibilidade:** sim. Define F a partir da E02. A familiaridade de quem montou a lista com os testes que falharam na E01 está declarada no protocolo.

**Fase do guia:** F4.2, F7.

---

### 2026-10-09 — Execução E02 (P1, P2 e diagnóstico P1L; 12 casos)

**Sintoma:** E02 concluída (20:07:59–20:26:49 UTC, 1.050 s), 36 tentativas (24 do desenho, 12 de diagnóstico), 0 erros. Métricas em `outputs/resultados_consolidados/E02_metricas.json` (`scripts/metricas_execucao.py`). Varredura da sessão igual à de setembro (15 × 15).

**Cache:** P1 e P2 têm os mesmos prompts da E01, então as 24 respostas do desenho vieram do cache (Seção 9, D8). Só os 12 P1L foram chamadas novas (US$ 0,01785; 17.887 + 6.684 tokens). Consequência: no desenho, a comparação E01 × E02 isola o efeito da separação F/D, sem variação da LLM.

**Resultados (desenho, cadeia reconstruída por definição):**
- Sem separação e `d_marcador`: TRV 0, nenhum caso aceito, como na E01.
- `d_criterio`: JS005, JS006 e JS011 aceitos com P1 (TRV por tentativa 0,143; 3/12 casos; TCD 1,00). Os três derrubam só testes D: 5 de SQL injection (b) em JS005 e JS006, 1 de SSTI (c) em JS011.
- A mudança em relação à E01 vem só da separação F/D: a reclassificação a posteriori da E01 dá exatamente os mesmos 3 casos.

**Diagnóstico P1L:** JS001 aceito com P1L em todas as definições. Com o alerta no prompt, a LLM corrigiu o segredo JWT; com P1 e P2 tinha alterado o redirecionamento. JS005 aceito com P1L sob `d_criterio`. JS006/P1L reprovou por um teste F: a correção reformatou a consulta em várias linhas, deslocando o comentário `vuln-code-snippet vuln-line`, e `vuln-code-snippet.test.ts › … returns a line-number hint …` falhou. JS012/P1L removeu a listagem de diretório (R = 0) e derrubou `ftp-folder.test.ts › GET serves a directory listing`, um dos testes sinalizados.

**Robustez:** a reexecução por timeout (Seção 7.2) atuou uma vez: JS005/P2, T4 travou na primeira rodada e passou na segunda. A reexecução por falha nova salvou JS002/P1 e JS007/P1 de testes intermitentes.

**Impacto na reprodutibilidade:** a E02 é a execução oficial do desenho com separação F/D. As 24 respostas do desenho são as da E01 (cache).

**Fase do guia:** F6, F7, F8.

---

### 2026-10-13 — Saídas reorganizadas por execução; prompts e validações das E01/E02 passam a ser versionados

**Sintoma:** `outputs/prompts/`, `codigos_corrigidos/`, `sast_depois/` e `testes/` misturavam artefatos de dry-run e de execução real. Para não versionar o dry-run, o `.gitignore` ignorava essas quatro pastas inteiras. Com isso, os prompts, os códigos corrigidos, as reanálises e as validações das E01 e E02 nunca foram versionados: só respostas, patches e o `execucoes.jsonl`, que apontava para arquivos ausentes do repositório.

**Causa:** a estrutura da F6 (entrada de 2026-10-07) separava por tipo de artefato, não por execução. O dry-run ia para `outputs/dry_run/`, mas o real ia direto para `outputs/<tipo>/`, sem uma pasta que o distinguisse.

**Correção:**
- Nova estrutura: `outputs/<EXECUCAO>/{prompts,respostas_llm,patches,codigos_corrigidos,sast_depois,testes}/`. Continuam comuns `outputs/sast_antes/` (baseline, catálogo e varreduras de sessão `<EXECUCAO>_baseline_raw.json`), `outputs/resultados_consolidados/` e `outputs/sondagens/`. O dry-run vai inteiro para `outputs/dry_run/`, inclusive o de `try_one.py` (antes em `outputs/tentativas/dry_run/`).
- `Saidas` em `run_pipeline.py` ganhou o método `t()` para artefatos da execução. `--execucao` passa a exigir o formato `E01`/`DRY01`, porque vira nome de pasta.
- Respostas e patches movidos com `git mv` (115 arquivos). Prompts, códigos corrigidos, reanálises e validações (225 arquivos), que nunca tinham sido versionados, foram movidos e adicionados.
- Em `execucoes.jsonl`, só os campos `artefatos.*` e `sast_depois_raw` foram reescritos para os novos caminhos (285 caminhos, todos conferidos como existentes). Os demais campos das 60 linhas foram conferidos como idênticos.
- O bloco de saídas do `.gitignore` virou uma linha: `outputs/dry_run/`. Também saíram `outputs/**/*.raw.json` e `outputs/**/*.tar.gz`, que não casavam com nenhum arquivo (os brutos se chamam `*_raw.json`). Nada rastreado precisou de `git rm --cached`, porque o dry-run nunca foi versionado.

**Impacto na reprodutibilidade:** positivo. Cada linha de `execucoes.jsonl` das E01/E02 agora tem prompt, resposta, patch, código corrigido, reanálise SAST e validação versionados. Os caminhos citados na entrada de 2026-10-07 (F6) passam a ser `outputs/<EXECUCAO>/<tipo>/`.

**Fase do guia:** F6.

---

### 2026-10-13 — Métricas por estratégia viciadas pela cadeia; duas leituras separadas

**Sintoma:** em `E02_metricas.json`, com `d_criterio`, o P1 aparecia com 3 aceites em 12 tentativas e o P2 com 0 em 9. O P2 parecia inútil.

**Causa:** `scripts/metricas_execucao.py` calculava as métricas por estratégia sobre a cadeia reconstruída, que corta as tentativas de um caso no primeiro aceite. O P2 só entrava nos 9 casos em que o P1 não tinha sido aceito. Nos dados brutos, o P2 rodou nos 12 casos (o orquestrador só interrompe no aceite sem separação, que não ocorreu) e foi aceito em JS005 e JS006.

**Correção:** o script passou a reportar (a) por estratégia, sobre todos os casos, e (b) cadeia sequencial. Protocolo, Seção 14. E01 e E02 recalculadas; (b) é idêntica ao cálculo anterior. E02, leitura (a):

| Definição | P1 aceitos | P1 TRV | P2 aceitos | P2 TRV |
|---|---|---:|---|---:|
| sem separação | 0/12 | 0,000 | 0/12 | 0,000 |
| `d_marcador` | 0/12 | 0,000 | 0/12 | 0,000 |
| `d_criterio` | 3/12 (JS005, JS006, JS011) | 0,250 | 2/12 (JS005, JS006) | 0,167 |

A diferença entre P1 e P2 em `d_criterio` é um caso só (JS011: o P2 não aplicou, âncora não encontrada). Com 12 casos isso não permite dizer que uma estratégia é melhor.

**Impacto na reprodutibilidade:** o formato de `<EXECUCAO>_metricas.json` mudou (`a_por_estrategia`, `b_cadeia`). Para a leitura (a) continuar completa com P3/P4, o orquestrador teria de rodar todas as estratégias em todos os casos (pendente de decisão do grupo, Seção 14).

**Fase do guia:** F7.

---

### 2026-10-13 — Sondagem: ampliar os rulesets de 5 para 11 (sem adotar)

**Motivação:** a Seção 3.4 do TCC 1 prevê tentativas sobre todos os alertas produzidos pela ferramenta. Cinco conjuntos de regras genéricos produziram só 12 achados elegíveis num projeto deliberadamente vulnerável. Ampliar a cobertura é mais fiel ao desenho original. Se o catálogo passar de cerca de 25 casos, entra o passo 6 do protocolo (amostragem estratificada por OWASP), pré-registrado e nunca usado.

**Execução:** `scripts/sondagem_rulesets.py` (novo), Semgrep 1.177.0 anônimo, `wt-1` limpo no commit fixado, mesmas exclusões. Antes, o script foi conferido contra o baseline oficial: reproduz 15 brutos e 12 elegíveis. Saídas em `outputs/sondagens/semgrep_2026-10-13/`. Nada em `outputs/sast_antes/` foi alterado.
- Controle (5 rulesets atuais, mesmo dia): 15 brutos, 12 elegíveis, os mesmos 15 triplos (regra, arquivo, linha) do oficial. O registro não mudou desde setembro para esses conjuntos.
- Ampliado (os 5 + `p/security-audit`, `p/secrets`, `p/xss`, `p/sql-injection`, `p/jwt`, `p/default`):

| Passo (Seção 3) | Contagem |
|---|---:|
| Brutos após exclusão de caminhos | 35 |
| 2. categoria `security` | 35 |
| 3. severidade (sai 1 INFO) | 34 |
| 4. com CWE | 34 |
| 5. dedupe `(check_id, path)` (7 duplicatas) | **27** |

Os 12 elegíveis oficiais continuam presentes; há 15 novos. Os 27 caem em 23 locais distintos: quatro locais têm duas regras (`login.ts:34`, `search.ts:23`, `redirect.ts:19`, `userProfile.ts:61`).
- Por sigla: XSS 5, OUTRO 4, PATHTRAV 4, SQLI 4, HARDCRED 3, CODEINJ 3, OPENREDIR 2, REDOS 1, INFOEXPOSURE 1.
- Por OWASP 2025: A05 12, A06 5, A01 3, A07 3, A04 2, A02 1, A08 1.
- CWEs fora de `config/mapa_cwe_vuln.yaml` (viram OUTRO): CWE-321 (2, JWT em `.spec.ts`), CWE-915 (1, `hacking-instructor`), CWE-522 (1, `routes/currentUser.ts`). Também aparece CWE-1333 (REDOS), que já está no mapa.

**Observações para a decisão (não aplicadas):**
1. Lacuna de escopo: o filtro da Seção 3 exclui `test/`, mas não testes do frontend (`*.spec.ts`), dados (`data/static/users.yml`) nem `frontend/src/hacking-instructor/`. Cinco dos 15 novos caem nesses arquivos ou em `lib/codingChallenges.ts`.
2. Como referência, só para consulta e sem adotar: a triagem manual da branch `semgrep-findings` classifica 7 dos 27 como falsos positivos e 1 como inconclusivo. Todos os 7 estão entre os 15 novos.
3. 27 passa de cerca de 25, então o passo 6 seria acionado.

**Impacto na reprodutibilidade:** nenhum no experimento (catálogo oficial inalterado). Os JSONs brutos ficam arquivados porque o registro não é versionado (D2).

**Fase do guia:** F3 (revisão).

---

### 2026-10-13 — Sondagem: Semgrep autenticado com os 5 rulesets atuais (sem adotar)

**Execução:** `semgrep login` (conta pessoal do Caio), mesma varredura do controle anônimo do mesmo dia: 5 rulesets, Semgrep 1.177.0, `wt-1` limpo, mesmas exclusões. Saída em `outputs/sondagens/semgrep_2026-10-13/autenticado_5rulesets/`. Uma primeira tentativa rodou antes de o login ser concluído (saiu anônima); foi descartada, porque não era versionada e o rótulo estava errado.

**Resultados, anônimo × autenticado:**

| Item | Anônimo | Autenticado |
|---|---:|---:|
| `extra.fingerprint` preenchido | 0/15 | 37/37 |
| `extra.lines` preenchido | 0/15 | 37/37 |
| Brutos | 15 | 37 |
| Regras disparadas | 7 | 16 |
| Elegíveis (Seção 3) | 12 | 29 |
| Erros reportados | 8 | 971 |

- Os 12 elegíveis oficiais continuam presentes; nenhuma regra deixou de disparar. Os 17 novos estão em 10 locais novos (6 rotas com `express-mongo-nosqli`, `lib/insecurity.ts:21` e `:192`, `routes/updateUserProfile.ts:42`, `models/index.ts:33`). Os outros caem em locais já do catálogo (`login.ts:34`, `search.ts:23`, `redirect.ts:19`, `userProfile.ts:61`). Nenhum cai em teste, dados ou `hacking-instructor`.
- **Causa da diferença:** com login, os mesmos `p/...` passam a incluir regras proprietárias (`metadata.semgrep.dev.rule.origin = pro_rules`, licença "Semgrep Rules License v1.0"). As 9 regras novas são todas desse tipo.
- **Os 971 erros:** 963 são "Internal matching error" de 3 regras proprietárias (`cryptojs-weak-algorithm`, `cors-default-config-express`, `cors-default-config-koa`). Elas usam um operador que, segundo a mensagem, "is only supported in the Pro engine", e falham em todos os arquivos no motor OSS (`engine_requested: OSS`). Ou seja, mesmo autenticado, parte das regras do conjunto não rodou. Os outros 8 são os mesmos avisos de parsing parcial do anônimo.
- CWEs fora do mapa: CWE-943 (6, NoSQL injection), CWE-732 (2), CWE-384 (2). Oito elegíveis ficam sem OWASP 2021 utilizável (só trazem rótulo 2017 ou nenhum).

**Implicações para a decisão (não aplicadas):**
1. Com `fingerprint` disponível, a assinatura D6 poderia ser revista. Ela usa `check_id|path` justamente porque o campo vinha vazio.
2. Reprodutibilidade: quem reproduzir precisa de conta no Semgrep, e as regras proprietárias não são públicas para cópia de referência (`config/semgrep-rules-referencia/`).
3. Enquanto o login estiver ativo nesta máquina, o pipeline também roda autenticado, o que contraria a Seção 2 ("sem login"). Para manter o protocolo, é preciso fazer `semgrep logout` antes de qualquer execução.

**Impacto na reprodutibilidade:** nenhum no experimento (catálogo oficial inalterado).

**Fase do guia:** F3 (revisão).

---

### 2026-10-13 — Catálogo v2: 11 rulesets anônimos, exclusões ampliadas, triagem manual, quarta definição de D e orquestrador sem interrupção

**Sintoma:** o catálogo v1 tinha 12 casos, amostra pequena para comparar estratégias. As sondagens do mesmo dia mostraram que a cobertura depende muito dos rulesets e do login.

**Causa:** cinco rulesets genéricos, anônimos, num alvo deliberadamente vulnerável.

**Correção (decisões do grupo, 2026-10-13):**
1. Catálogo oficial com os 11 rulesets, anônimo. O login não foi adotado, por quatro motivos: as regras proprietárias não podem ser inspecionadas nem versionadas na pasta de referência; três delas falharam em todos os arquivos por exigirem o motor pago; reproduzir o trabalho passaria a exigir conta no Semgrep; e o ganho do `fingerprint` só se realizaria trocando o passo 5, que é pré-registrado. Protocolo, Seção 2. `semgrep logout` conferido antes da varredura oficial (`semgrep show identity`: não logado).
2. A sondagem do login virou a Seção 15 do protocolo, como resultado para a Discussão.
3. Exclusões novas em `config/semgrepignore`: `*.spec.ts`, `data/static/users.yml`, `frontend/src/hacking-instructor/`, `lib/codingChallenges.ts`. Elas falham no critério de código da aplicação coberto pela suíte (Seção 3, passo 1). Removem 7 dos 35 brutos.
4. Campo `triagem_manual` no catálogo (`config/triagem_manual.yaml`), sem excluir nenhum caso; as métricas reportam os grupos à parte (Seção 3, passo 7). A triagem une dois arquivos da branch `semgrep-findings` (commit `fa04444`), sem conflito entre eles: 35 alertas de regras do registro.
5. CWEs mapeadas: CWE-321 → HARDCRED, CWE-522 → CREDPROT (nova), CWE-915 → MASSASSIGN (nova). Os 4 achados que estavam em OUTRO na sondagem eram exatamente essas CWEs: 2 × CWE-321 em `*.spec.ts`, CWE-915 em `hacking-instructor/helpers/helpers.ts` e CWE-522 em `routes/currentUser.ts`. Os três primeiros saíram pelas exclusões. No v2, nenhum caso fica em OUTRO.
6. `N_max` refeito com dados reais (Seção 16): o mínimo é cerca de 47 casos (tempo, sequencial); o passo 6 não dispara para 22.
7. O orquestrador roda todas as estratégias em todos os casos; a cadeia é reconstruída nas métricas (Seção 14).
8. Quarta definição `d_criterio_amplo` (Seção 13, item 8), com as métricas da E01 e E02 refeitas nas quatro definições.
9. Catálogo v2 gerado (Seção 3, "Resultado do catálogo v2"): 22 casos, IDs JS001–JS012 mantidos por assinatura, JS013–JS022 novos.

**Arquivamento do v1.** `git mv` de `outputs/sast_antes/{baseline_raw,catalogo_issues,catalogo_meta,relatorio_baseline}` para `*_v1`. **As execuções E01 e E02 se referem ao catálogo v1** (`catalogo_issues_v1.json`, baseline de setembro `baseline_raw_v1.json`). O caminho do baseline foi atualizado em `E01_comparacao_baseline.json`, `E02_comparacao_baseline.json` e nos resumos das sondagens. Os 12 casos do v1 estão no v2 com o mesmo ID e a mesma assinatura. Para eles, as métricas da E01/E02 usam a triagem do v2 (11 confirmados, 1 inconclusivo: JS007).

**Pasta de referência das regras.** As 7 regras novas do v2 foram copiadas do mesmo commit do `semgrep-rules` (`a84ff9c`), para preencher `modo_regra` (12 `taint`, 10 `search`).

**Correção de uma afirmação anterior:** a entrada "Sondagem: ampliar os rulesets" diz que a triagem da branch classifica 7 dos 27 como falsos positivos. Com o segundo arquivo da branch (`config/auditoria_desafios.yaml`, que cobre `p/security-audit`), são 10: os 3 alertas `unquoted-attribute-var` também foram julgados falsos positivos. No v2, depois das exclusões, ficam 6 falsos positivos (JS013, JS014, JS016, JS020, JS021, JS022).

**Pendências antes da E03:** `MAX_LLM_CALLS = 60` deixa só 27 chamadas (Seção 16). `CREDPROT` (JS017) não tem categoria de RAG. Faltam a base de conhecimento e os testes de regressão de segurança.

**Impacto na reprodutibilidade:** muda a população do experimento a partir da E03 (v2). E01 e E02 continuam válidas e reprodutíveis sobre o v1 arquivado.

**Fase do guia:** F3, F6, F7.

---

### 2026-10-16 — Reversão de 13/10 apagou artefatos da E01/E02; recuperação pelo `.git` e trabalho de 13/10 refeito

**Sintoma:** em 13/10, o Caio desfez de propósito o trabalho do dia, para alinhar com a dupla. Em 16/10 decidiu refazê-lo. `outputs/E01/` e `outputs/E02/` estavam vazias: os 225 artefatos não commitados (prompts, códigos corrigidos, reanálises SAST e validações) tinham sumido. Também sumiram o `config/semgrep-rules-referencia/README.md` (nunca versionado) e os JSONs das sondagens de 13/10.

**Causa:** na reorganização de 13/10, esses arquivos (antes ignorados pelo `.gitignore`) foram movidos e adicionados ao índice com `git add`, sem commit. A reversão descartou o índice e, com ele, os arquivos novos. O README e as sondagens eram arquivos não versionados e não foram adicionados.

**Correção:**
- **Recuperação pelo `.git`.** `git add` grava o conteúdo como objeto, que continua no `.git` até a limpeza (duas semanas). `git fsck --unreachable` listou 186 objetos órfãos. Cada um foi identificado pelo conteúdo e casado com sua tentativa no `execucoes.jsonl`:
  - 60 prompts: 58 por `hash_prompt`. Os 2 restantes (JS003/P1, JS005/JS006 P1) não estavam órfãos porque um arquivo idêntico existe na branch `semgrep-findings` (commit `c1e1f44`, dry-run do Matheus com o mesmo construtor e o mesmo cache); confirmados pelo `hash_prompt` e pelo formato exato de gravação do orquestrador.
  - 55 validações: casadas pela duração (única); conferidos F, camada de falha e testes falhos de cada uma.
  - 55 reanálises SAST: casadas pelos achados. 49 estão em grupos de tentativas do mesmo caso com achados idênticos; nesses, o desempate foi pelo tempo, e só o perfil de tempo pode ter ficado trocado entre elas.
  - 55 códigos corrigidos: regenerados aplicando cada patch versionado ao arquivo original do commit fixado; os 55 são idênticos byte a byte a objetos do `.git`.
  - Conferência final: as métricas da E01/E02, refeitas camada por camada a partir das validações recuperadas, bateram com todos os F gravados.
- Caderno e protocolo restaurados de objetos órfãos (versões finais de 13/10: só acréscimos sobre o commit `d645466`). O README da pasta de referência foi recriado a partir do conteúdo lido na conversa de 13/10. Guia, adendo e `CLAUDE.md`, não versionados, não tinham sido afetados.
- Código refeito a partir do registro da sessão de 13/10: orquestrador, runner, `conjunto_d`, `semgrep_client`, `build_issue_catalog`, `metricas_execucao`, `try_one`, `sondagem_rulesets` (agora com `--exclusoes` e `--referencia`), `config/semgrepignore`, `mapa_cwe_vuln.yaml`, `conjunto_d_amplo.json`, `triagem_manual.yaml` (mesmas fontes, sem mudança entre `fa04444` e `c1e1f44`) e as 7 regras de referência (mesmo commit).
- Reprocessamento: sondagens anônimas refeitas em `outputs/sondagens/semgrep_2026-10-16/` (5 rulesets: 15 brutos / 12 elegíveis; 11 rulesets com as exclusões antigas: 35 / 27, iguais a 13/10). A sondagem com login **não foi refeita** (decisão do Caio: não usar login); a Seção 15 do protocolo fica com os números de 13/10, sem JSON bruto. Baseline e catálogo v2 regenerados: idênticos a 13/10 em todas as contagens (28 brutos, 22 elegíveis, IDs, siglas, triagem). Métricas da E01/E02: idênticas a 13/10.
- `MAX_LLM_CALLS` de 60 para 150 no `.env`, para a E03 (decisão do Caio).

**Incidente operacional:** o primeiro dry-run (DRY04) ficou parado das 19:48 às 21:04 sem erro. O Mac estava em repouso (`pmset -g log`: repouso por inatividade de 1 min, depois tampa fechada na bateria). O `time.monotonic()` do Python não conta o tempo dormindo no macOS, então a duração medida (80 s) não acusou nada. Execuções longas passam a rodar com `caffeinate -is` e o Mac na tomada, com a tampa aberta (`caffeinate` não impede o repouso com a tampa fechada na bateria).

**Impacto na reprodutibilidade:** os artefatos da E01/E02 voltaram com a ressalva acima sobre o perfil de tempo de 49 reanálises. Daqui em diante, resultado de execução é commitado logo depois de gerado.

**Fase do guia:** F6, F7.

---

<!--
Próxima entrada:

### AAAA-MM-DD — título

**Sintoma:**
**Causa:**
**Correção:**
**Impacto na reprodutibilidade:**
**Fase do guia:**
-->

============================================================
Resumo -- cole isto no caderno de laboratorio (F2.4):

T0_compilacao: 1.5s (passou)
T2_arquivo_unico: 0.2s (passou)
T3_suite_unitaria: 1.9s (passou)
T4_api: 13.0s (FALHOU)
T5_desafio_cypress: 7.3s (passou)