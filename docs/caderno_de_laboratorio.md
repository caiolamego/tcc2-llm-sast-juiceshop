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

**Sintoma:** `scripts/setup/setup_target.sh` falhava no passo `[4/4]` (instalação de dependências) com erro do `npm ci` exigindo um lockfile existente.

**Causa:** o repositório upstream do OWASP Juice Shop lista `package-lock.json` no próprio `.gitignore` — o lockfile não é versionado no projeto. `npm ci` exige um `package-lock.json` presente e falha sem ele. Não é incompatibilidade de plataforma: acontece em qualquer máquina.

Um segundo erro apareceu ao tentar `npm install` manualmente como workaround: falhou por ter sido executado na raiz do repositório do TCC (onde não há `package.json` de aplicação), e não dentro do worktree do alvo (`workspace/wt-1`).

**Correção:** `scripts/setup/setup_target.sh` alterado de `npm ci --no-audit --no-fund` para `npm install --no-audit --no-fund`. O comando roda dentro da subshell `( cd "$WT" && ... )`, então, executado via script, sempre acontece no diretório correto — o segundo erro só ocorre se o comando for repetido manualmente fora do script.

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

- `scripts/experiment/measure_validation_cost.py` alterado para não subir servidor antes de T4 — ele passa a rodar no mesmo grupo de T0/T2/T3, sem servidor pré-iniciado. Servidor pré-iniciado fica reservado só para T5 (Cypress), que precisa de uma URL real para o navegador visitar. Resolve o item 3.
- **Decisão do grupo:** padronizar `TZ=UTC` como variável de ambiente fixa em todo comando que roda testes do Juice Shop (T2 a T5), em vez de implementar comparação de baseline no runner de validação. Resolve o item 1 (confirmado: 333/333 com `TZ=UTC`, 0 falhas). Registrar em `config/config.yaml` e nos comandos de `src/pipeline/validation/runner.py` quando F4 for construído.

**Impacto na reprodutibilidade:** sim.

Sobre o item 1 (fuso horário): resolvido pela padronização de `TZ=UTC`. Precisa constar na seção de Metodologia/Limitações do TCC 2 como ajuste de ambiente necessário para reprodutibilidade entre fusos horários diferentes — sem isso, o mesmo pipeline produziria `Fⱼ = 0` para qualquer correção rodada por alguém em fuso negativo (Américas), mesmo sem nenhuma relação com a correção em si.

Sobre o item 2 (rede externa): **`TZ=UTC` não resolve isso.** O grupo decidiu, por ora, não implementar o mecanismo de baseline por conjunto de falhas (comparar testes que já falhavam antes da correção vs. depois) que resolveria também esse caso. Ou seja: testes com dependência de rede externa (como o do StackOverflow) continuam sendo uma fonte de ruído não tratada — se aparecerem de novo durante a execução completa do experimento, vão gerar falsos `Fⱼ = 0`. Fica como risco conhecido e aceito, não como pendência esquecida.

**Correção de acompanhamento (mesmo dia):** a decisão de `TZ=UTC` tinha sido registrada aqui e no guia, mas não tinha sido de fato aplicada em `scripts/experiment/measure_validation_cost.py` — o script continuou chamando os comandos sem a variável. Confirmado numa segunda execução em `workspace/wt-1`: T3 falhou de novo com o mesmo erro de fuso horário, e T4 já mostrava só a falha de rede isolada (confirmando que a correção do conflito de porta, essa sim, funcionou). Corrigido adicionando `os.environ["TZ"] = "UTC"` logo após os imports do script, antes de qualquer `subprocess.run`/`Popen` — processos filhos herdam o ambiente do pai, então isso basta para propagar a variável para `npm`, `npx` e `node` sem precisar alterar cada chamada individualmente. **Confirmado numa terceira execução via script** (não mais manual): T0/T2/T3/T5 passaram, T3 fechou em 0 falhas — só T4 manteve a falha de rede já conhecida e aceita. Incidente encerrado.

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

**Correção:** `SEVERIDADES_ACEITAS` em `scripts/experiment/build_issue_catalog.py` ampliado para `{"ERROR", "WARNING", "CRITICAL", "HIGH", "MEDIUM"}`, cobrindo os dois esquemas e excluindo apenas o nível mais baixo em qualquer um deles (`INFO`/`LOW`). O passo 3 do protocolo de filtragem em D1 do guia também foi reescrito para descrever essa equivalência explicitamente.

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

**Correção (decisão do grupo, opção 2):** linha de base de referência. `scripts/experiment/baseline_testes.py` roda T3 e T4 num worktree sem alteração e grava `outputs/baseline_testes.json` (commit do alvo, data, versão do Node, nome de cada teste falho). No runner, cada tier de teste passa quando o conjunto de testes falhos está contido no da linha de base; cada validação registra `testes_falhos_novos`. Nenhum teste é pulado por nome. Os nomes vêm do reporter JUnit do `node --test`, chamado com os mesmos argumentos dos scripts `test:server`/`test:api` do `package.json` (o `npm run ... --` colocaria as flags depois do glob). O runner confere que a linha de base foi gerada no mesmo commit do worktree.

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

### 2026-10-18 — Ambiente dependente da máquina; adoção de um ambiente único em Docker (F2)

**Sintoma:** na branch `semgrep-findings`, o preflight no Mac do Caio falhou com `FileNotFoundError: workspace/wt-1/package-lock.json`, e 15 testes Python falharam ou deram erro no macOS: a publicação exclusiva das métricas usa `renameat2`, que não existe fora do Linux (ENOTSUP), e há caminhos comparados como `/var` × `/private/var`. O baseline funcional `outputs/revalidacoes/PILOTO10_CORRECAO_V1/BASELINE` só vale no ambiente em que foi gerado, porque registra as versões, o hash do lockfile e o hash das dependências instaladas.

**Causa:** o ambiente variava de máquina para máquina. O Node local era v26.7.0 e o do baseline, v24.14.0. O Juice Shop não versiona lockfile (o `.npmrc` tem `package-lock=false`), então cada `npm install` resolve as dependências na data em que roda. E o `renameat2` só existe no Linux.

**Correção:** ambiente único em Docker (branch `feat/docker`, guia em `docs/docker.md`). Arquivos: `Dockerfile`, `compose.yaml`, `.dockerignore`, `docker/gerar_lockfiles.sh`, `docker/preparar_workspace.sh` e alvos `docker-*` no `Makefile`. O que fica fixo:
- plataforma `linux/amd64` (Rosetta nos Macs Apple Silicon);
- imagem `node:24.14.0-bookworm`, fixada pelo digest;
- Python 3.11.2 da imagem, com os pacotes Python (incluindo o Semgrep 1.177.0) travados em `requirements.lock.txt`;
- Juice Shop no commit `f915bddd…`, com lockfiles gerados uma única vez (2026-10-18T20:06:59Z, npm 11.9.0) e versionados em `docker/juice-shop/`;
- `TZ=UTC`.

As worktrees `wt-1..wt-K` são cópias exatas (`cp -a`) do Juice Shop de referência da imagem, num volume do Docker. O `preparar_workspace.sh` também cria `workspace/catalogo-alvo` (checkout limpo), exigido pelo teste `test_recompare_archived_scans`. O painel ganhou `--endereco 0.0.0.0`, usado só dentro do container; o compose publica a porta apenas em `127.0.0.1`.

Verificação no container:
- imagem construída;
- 315 testes Python OK, incluindo 2 que eram pulados no Mac;
- `semgrep --test rules` 28/28;
- identidade de ambiente igual nas 4 worktrees (`b11c70b9…`);
- consolidação de métricas do piloto `AMP_PAINEL_20261017T064627Z_bf4efba0` refeita: os 14 artefatos saíram idênticos byte a byte aos arquivados;
- painel respondendo;
- com o baseline do Docker (`DOCKER_V2`, entrada seguinte), o preflight dos 10 casos do piloto passou: 40 prompts e baseline SAST reproduzido (78 de 78). Os campos do contrato que dependem do ambiente (casos, catálogo, perfil, versão do Semgrep, componentes dos prompts, RAG) são iguais aos do piloto. O `prompts_validacao_sha256` difere só porque o `runner.py` mudou no commit `d03fe57`, depois do piloto;
- dry-run completo, sem LLM (P1 a P4, K=4, `relacionada_v2`): 40 tentativas, todas `R0F1M1` com comparação SAST conclusiva, 0 erros, US$ 0, 15 artefatos de métricas, 15min34s. As worktrees voltaram limpas. Saída em `.cache/teste_docker/` (não versionada).

**Impacto na reprodutibilidade:** sim, positivo, mas com quebra de continuidade. Daqui em diante, as execuções oficiais devem rodar no container. Os resultados anteriores (E01 a E03 e o piloto de 10 casos) foram gerados em outros ambientes e têm outra identidade de ambiente; não devem ser misturados sem registro. Limitação que continua: os pacotes do sistema (apt) não são fixados, então reconstruir a imagem em outra data pode trazê-los um pouco diferentes. Mitigação proposta: publicar a imagem num registro e citá-la pelo digest.

**Fase do guia:** F2 (ambiente e preparação do alvo). O guia ainda não tem o passo com Docker.

---

### 2026-10-18 — `npm rebuild` executa o `postinstall` da raiz; `libxmljs2` compilado do fonte (F2)

**Sintoma:** no primeiro build da imagem, a checagem `test ! -e frontend/node_modules` falhou depois de `npm ci --package-lock=true --ignore-scripts && npm rebuild`.

**Causa:** o `npm rebuild` também executa os scripts de ciclo de vida do próprio pacote raiz. O `postinstall` do Juice Shop roda `cd frontend && npm install`, o que instalaria o frontend sem lockfile (o `.npmrc` o desliga) e anularia a fixação das versões. A suposição de que o `rebuild` só tocava nas dependências estava errada; o comportamento foi reproduzido num container descartável.

**Correção:** o `postinstall` sai do `package.json` só durante o `npm ci` (`npm pkg delete scripts.postinstall`). O `npm ci` continua rodando os scripts das dependências (binários nativos). Depois, o `package.json` é restaurado com `git checkout` e o build exige `git status` limpo. O frontend é instalado à parte, com `npm ci --package-lock=true`, e os builds usam os mesmos comandos do `postinstall` original. Na mesma investigação: o binário pré-compilado do `libxmljs2` exige GLIBC 2.38 e o bookworm tem 2.36, então o `libxmljs2` é compilado do fonte durante o build da imagem.

**Impacto na reprodutibilidade:** seria alto (frontend sem lockfile), mas foi corrigido antes de qualquer execução. O binário compilado do `libxmljs2` faz parte da imagem: outra construção pode compilá-lo de outro jeito, o que é mais um motivo para citar a imagem pelo digest.

**Fase do guia:** F2.

---

### 2026-10-18 — No Docker, o Juice Shop desliga sozinho 17 desafios (`safetyMode: auto`) (F2/F4)

**Sintoma:** o primeiro baseline funcional gerado no container (`outputs/revalidacoes/DOCKER_V1/BASELINE`) teve os 39 grupos comparáveis. Mas, comparado ao baseline do piloto (`outputs/revalidacoes/PILOTO10_CORRECAO_V1/BASELINE`), havia 10 testes em 8 grupos que passavam no ambiente do Matheus e falhavam no container:
- b2b (3 testes);
- current_user, feedback, login, product, profile, track e upload (1 cada).

Exemplo: o teste de login "saved as remote IP when True-Client-IP is not present" recebeu `''` em vez de `'127.0.0.1'`. A comparação completa está em `outputs/revalidacoes/DOCKER_V1/comparacao_baseline_piloto10.json`.

**Causa:** o `config/default.yml` do Juice Shop traz `challenges.safetyMode: auto`. Nesse modo, `lib/utils.ts` (`isChallengeEnabled`) desliga os desafios cujo `disabledEnv` inclui `Docker` quando `lib/is-docker.ts` detecta um container (`/.dockerenv`, cgroup ou mountinfo). O `data/static/challenges.yml` marca 17 desafios assim:

> restfulXss, fileWrite, rce, usernameXss, persistedXssUser, httpHeaderXss, noSqlCommand, noSqlOrders, reflectedXss, ssti, persistedXssFeedback, rceOccupy, videoXss, xxeFileDisclosure, xxeDos, yamlBomb e lfr

Os 10 testes que falharam correspondem a 9 desses desafios. Fora de container, o modo `auto` mantém todos ligados; por isso o ambiente do Matheus não tinha o problema. Sem correção, o alvo no Docker teria 17 vulnerabilidades desativadas em tempo de execução. O SAST, que é estático, não muda, mas os testes funcionais e o conjunto D mudam, e o alvo deixa de ser o alvo estudado.

**Correção:** o `Dockerfile` define `ENV NODE_CONFIG='{"challenges":{"safetyMode":"disabled"}}'`. É a opção oficial do Juice Shop, a mesma de `config/unsafe.yml` e `config/ctf.yml`, e o pacote `config` (3.3.12) a aplica por cima de `config/test.yml`. A trava tem três partes:
1. o build confere o valor efetivo com `NODE_ENV=test` e falha se não for `disabled`;
2. o valor fica registrado em `/opt/ambiente.json`;
3. a variável já faz parte de `identity.ambiente` (`variaveis_sha256`), então um container sem ela é recusado pelo preflight.

O runner repassa as variáveis do processo aos testes (`llm/provider.py::ambiente_alvo`, que remove só as credenciais da LLM). O baseline foi refeito em `outputs/revalidacoes/DOCKER_V2/BASELINE`: os 39 grupos são equivalentes aos do piloto (mesmos testes, estados, falhas e obrigatórios aprovados). A comparação está em `outputs/revalidacoes/DOCKER_V2/comparacao_baseline_piloto10.json`, gerada por `scripts/audit/compare_functional_baselines.py`. O `DOCKER_V1` fica como evidência deste incidente e não deve ser usado; o preflight o recusaria, porque o `variaveis_sha256` dele é outro.

**Impacto na reprodutibilidade:** alto, se não for corrigido. Quem rodar o Juice Shop em container sem `safetyMode: disabled`, inclusive com a imagem oficial do projeto, mede um alvo diferente. Isso precisa constar no protocolo como cuidado obrigatório.

**Fase do guia:** F2 (ambiente) e F4 (validação, linha de base do F).

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