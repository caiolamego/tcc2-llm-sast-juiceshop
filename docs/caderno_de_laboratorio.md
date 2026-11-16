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

### 2026-10-26 — Reorganização do repositório sem mudança de funcionamento (F1)

**Sintoma:** os autores não conseguiam mais se localizar no repositório:
- 7.049 dos ~7.400 arquivos versionados estavam em `outputs/`, misturando a campanha oficial, pilotos, testes de desenvolvimento e o histórico E01–E03;
- 30 documentos, mais `features/` e um README de 31 KB, se sobrepunham;
- `frontend/` na raiz era o painel, não o frontend do Juice Shop;
- nenhum lugar ligava o código às etapas do §3.8 do TCC.

**Causa:** o repositório cresceu por acúmulo durante as features 01–07, sem uma regra de onde cada tipo de arquivo deveria ficar.

**Correção:** o Caio escolheu duas opções combinadas: arquitetura "dutos e filtros" para o código e organização do repositório pelo papel de cada coisa (compêndio de pesquisa). A exigência era não alterar nada no funcionamento.

O levantamento mostrou que boa parte do repositório faz parte da identidade científica e não pode mudar de nome, pasta ou conteúdo:
- **baseline oficial:** guarda o nome e o conteúdo de 5 arquivos de `validation/`;
- **referência Docker:** confere 17 arquivos por caminho;
- **contrato da execução:** registra os caminhos de `validation/`, `sast/`, `target/`, `patching/` e de 4 módulos da raiz de `src/pipeline/`;
- **caminhos fixos no código:** `config/conjunto_d.json` e `outputs/baseline_testes.json`;
- **arquivos congelados que citam documentos:** `docs/docker.md`, `docs/criterios_conjunto_d.md` e `docs/conjunto_d.md`.

Por isso, ficaram onde estavam `src/pipeline/` (módulos), `config/`, `tests/`, `rules/`, `scripts/` (seus nomes aparecem em centenas de registros de `outputs/` como comando gerador) e `outputs/`.

Feito:
- **Arquitetura documentada por etapa.** `src/pipeline/README.md`: etapa do TCC → filtros (módulos) → artefatos de entrada e saída, com a explicação dos nomes fixos.
- **Índices novos:** `README.md` (curto), `docs/README.md`, `config/README.md`, `scripts/README.md`, `outputs/README.md` e `docs/historico/README.md`, com a tabela caminho antigo → novo.
- **Arquivos movidos:**
  - `features/` → `docs/historico/features/`;
  - 4 guias de uso → `docs/guias/`;
  - `GUIA_CONTINUIDADE_TCC2.md` → `docs/planejamento/`;
  - `estrutura_projeto.md` → `docs/historico/`;
  - README anterior → `docs/guias/referencia_detalhada.md`;
  - `frontend/painel/` → `src/pipeline/painel/web/`.
- **Código alterado:** só uma linha, o caminho da interface em `src/pipeline/painel/server.py`.
- **Links:** corrigidos em 24 documentos. Nos documentos históricos só os links mudaram; os comandos registrados ficaram como foram executados.
- **Modo histórico** (E01–E03): ficou no lugar, marcado como legado nos índices.

Achado durante o levantamento: `config/perfis/ampliado_v1/` não carrega com o código atual ("Hash de regra inválido"). Nenhuma configuração o usa; a campanha usa `ampliado_piloto_v1`.

Verificação antes × depois (imagem local e baseline `DOCKER_V2`, sem LLM), com evidência em `outputs/revalidacoes/REORGANIZACAO_20261026/`. Ficou idêntico:
- a identidade científica: componentes, cobertura, prompts, RAG, perfis, catálogo e as 17 entradas da referência Docker;
- os 358 testes Python e os 28 testes de regras;
- o preflight dos 52 casos, com 208 prompts idênticos byte a byte;
- a reconsolidação das métricas da campanha oficial, idêntica ao arquivado;
- o dry-run de 10 casos: 40 tentativas com os mesmos R, F, M e classificação, e prompts, respostas, patches, códigos corrigidos e comparações idênticos byte a byte;
- o painel, o `make -n` de todos os alvos e os comandos do `executar.py`;
- os links: 0 internos quebrados, e os 3 externos com o mesmo destino.

As únicas diferenças entre execuções foram tempos, a pasta temporária, o ID do container e a worktree sorteada para cada tentativa. Elas aparecem também entre duas execuções seguidas sem mudança nenhuma.

**Impacto na reprodutibilidade:** nenhum na execução. Registros antigos em `outputs/` e relatórios de auditoria continuam citando caminhos antigos de documentação; a correspondência está em `docs/historico/README.md`. A conferência da imagem oficial (`make docker-check`) não pôde rodar nesta máquina, porque a imagem está só com o Matheus. Mas as 17 entradas que ela confere ficaram com o mesmo caminho e o mesmo hash.

**Fase do guia:** F1 (repositório).

---

### 2026-10-26 — Reorganização do código por etapas e referência oficial v2 (F1/F2)

**Sintoma:** na reorganização anterior (mesmo dia), os módulos de código não puderam ser movidos nem renomeados, porque o nome e o conteúdo de parte deles entram na identidade científica (baseline oficial, referência Docker, contrato). A arquitetura de dutos e filtros ficou só documentada, e os nomes continuaram misturando português e inglês.

**Causa:** a identidade científica amarra o código ao baseline. Qualquer mudança em `validation/coverage.py`, `coverage_runner.py`, `conjunto_d.py`, `preparacao_api.py`, `coverage_api_setup.mjs`, `runner.py` ou `identity.py` invalida o baseline e a referência oficiais, cuja imagem estava só na máquina do Matheus.

**Correção:** com autorização do Caio para gerar um baseline novo:

1. **Código** (`src/pipeline/`), movido para uma pasta por etapa:
   - `etapas/e01_analise_sast` … `e09_metricas`;
   - `orquestracao/` (`campanha.py`, `preflight.py`), `comum/` e `legado/`;
   - nomes em português (tabela completa em `docs/historico/README.md`);
   - nenhuma função, classe ou lógica mudou: só arquivos, pastas, imports, alvos de `mock.patch` e os nomes de arquivo usados nas identidades (`provedor.py` do Colab, adaptadores de `cobertura.py`, `componentes.py`, `docker/referencia.py`);
   - quatro módulos recalculam a raiz do projeto a partir de `__file__` e tiveram a profundidade ajustada.
2. **Scripts:** pastas `preparacao/`, `experimento/`, `relatorios/`, `auditoria/` e nomes em português.
3. **O que ficou no lugar:** `config/`, `knowledge_base/`, `rules/`, `tests/` e `outputs/`. O catálogo arquivado e o leitor de métricas conferem esses caminhos, e mudá-los impediria reconsolidar a campanha de 19/10.
4. **Referência Docker:**
   - a anterior foi arquivada em `docker/historico/referencia_oficial_v1.json`;
   - `make docker-baseline` gerou `outputs/baselines/docker/oficial_v2/`, com a imagem local (`sha256:81fe6403…`, mesmo `Dockerfile` e mesmos lockfiles);
   - a trava de equivalência de `docker/referencia.py` passou a aceitar diferença **só** em `adaptadores_sha256`, os hashes do código; para isso, `comparar_baselines_funcionais.py` passou a informar quais campos da cobertura diferem;
   - continua exigindo os 39 grupos equivalentes, as compilações aprovadas e a revisão, o mapa, o conjunto D e os testes adicionais iguais.
   - Resultado: 39/39 grupos equivalentes ao `DOCKER_V2`, ambiente idêntico, ambiente e grupos conferidos, referência congelada.
5. **Configurações:** `config/execucao_docker_preparados.yaml` e `execucao_docker_78.yaml` passaram a apontar para `oficial_v2`.

Verificação antes × depois (sem LLM; evidência em `outputs/revalidacoes/REORGANIZACAO_20261026/fase2_codigo/`). Ficou idêntico:
- os textos e a política de contexto dos prompts, o roteiro, a base RAG, os perfis SAST e o catálogo;
- a identidade de cobertura, fora os hashes dos 5 adaptadores renomeados;
- as 10 entradas não-código da referência;
- os 358 testes Python, com os mesmos resultados, e os 28 testes de regras;
- o preflight dos 52 casos, com 208 prompts idênticos byte a byte;
- o dry-run de 10 casos: 40 tentativas com os mesmos R, F, M, classificação e hash do prompt, e prompts, respostas, patches, códigos corrigidos e comparações idênticos byte a byte;
- os CSVs de métricas;
- a reconsolidação da campanha oficial, idêntica ao arquivado;
- o painel, o `make -n` (fora o ID da imagem) e os comandos do `executar.py` (fora os nomes novos);
- os 99 módulos e scripts, que importam um a um;
- os links: 0 internos quebrados.

Mudaram só as identidades esperadas: `validacao`, `prompts_validacao_sha256`, `inferencia` e `baseline_testes_sha256` no contrato. `make docker-check` passou a funcionar nesta máquina.

**Impacto na reprodutibilidade:** a campanha de 19/10 continua ligada à referência v1 (imagem do Matheus, baseline `oficial_v1`) e foi reconsolidada sem diferença. Execuções novas usam a v2, e o Matheus e a banca precisam da imagem nova (`make docker-export` / `make docker-import`). Execuções antigas não podem ser retomadas com o código novo, o que é esperado, porque estão concluídas. As respostas da OpenAI em cache continuam válidas, porque a chave é só prompt, modelo e seed. O cache do Colab inclui a identidade da implementação e deixa de ser reaproveitado; ele não foi usado na campanha. Registros antigos em `outputs/` e relatórios de auditoria citam nomes antigos; a correspondência está em `docs/historico/README.md`.

**Fase do guia:** F1 (repositório) e F2 (ambiente).

---

### 2026-11-01 — Retirada do modo histórico (E01–E03) do código (F1)

**Sintoma:** `src/pipeline/etapas/e01_analise_sast/semgrep.py` tinha duas gerações de código: rulesets do registro com assinatura `sha256(check_id|caminho)` (D6) e a varredura por perfil congelado. O orquestrador mantinha os dois modos, e o histórico ainda era o padrão de `--catalogo`. Só a campanha atual (catálogo por ocorrência) é executada.

**Causa:** na reorganização de 26/10, o modo histórico ficou no lugar, só marcado como legado. Depois disso, ele só servia para refazer E01–E03. Para isso, de todo modo, é preciso voltar ao commit de cada execução, porque o código já tinha mudado de caminho.

**Correção:** decisão do Caio, retirar o que o modo atual não usa.
- **Tags git** nos commits de cada execução: `e01-preliminar` (`3b7ef48`), `e02-oficial-catalogo-v1` (`da10b26`), `e03-catalogo-v2` (`fa7b644`, só na `feat/p3-p4`), e `modo-historico-final` (`b52356e`), o último commit com o modo histórico na estrutura reorganizada.
- **Código retirado:**
  - de `semgrep.py`: `RULESETS`, `assinatura`, `ler_exclusoes`, `executar` e `carregar_resultados`;
  - `legado/filtro.py`;
  - `resposta_falsa`;
  - do orquestrador: a varredura da sessão e o ramo não ampliado. `--catalogo` passou a ser obrigatório, e o catálogo histórico é recusado com mensagem que indica a tag.
- **Scripts retirados:** `gerar_catalogo_historico.py`, `marcar_desafios_historicos.py`, `validar_cenarios_camadas.py`, `medir_custo_validacao.py` e `relatorio_baseline_historico.py`.
- **`tentar_um_caso.py` e `sondagem_sast.py`:** perderam só o ramo histórico; já funcionavam com o catálogo atual.
- **Mantidos, apesar do rótulo "legado":**
  - `legado/comparacao_v1.py`, que o comparador v2, o preflight e a medição importam;
  - `camadas.py`, conferido pela referência Docker;
  - `gerar_linha_de_base_historica.py`, citado por `camadas.py`;
  - `metricas_historicas.py` e a leitura de E01/E02 em `e09_metricas`, que os testes usam para conferir os números arquivados;
  - `preparar_alvo.sh`, porque `config/execucao.yaml` ainda roda fora do Docker.
- **Testes:** dois testes montavam o orquestrador no modo histórico (`test_colab_contract`, `test_painel`). Mudou só a preparação; as asserções são as mesmas.

Verificação antes × depois (Docker, sem LLM; evidência em `outputs/revalidacoes/LIMPEZA_MODO_HISTORICO_20261101/`). Ficou idêntico:
- os 358 testes Python e os 28 testes de regras;
- o preflight dos 52 casos, com 208 prompts idênticos byte a byte;
- o dry-run de 10 casos: as 40 tentativas têm registros iguais campo a campo, fora tempos e hashes derivados. Prompts, respostas, patches, códigos corrigidos e comparações são idênticos byte a byte;
- a reconsolidação da campanha oficial, idêntica ao arquivado;
- o painel, o `make -n` e os comandos do `executar.py`;
- a referência Docker e o baseline oficial;
- os links: 0 internos quebrados.

Mudaram só a lista de arquivos do código no contrato (de 30 para 29) e o que deriva dela: `contrato_execucao_sha256` e as chaves do cache de validação.

**Impacto na reprodutibilidade:** nenhum nas execuções atuais. Uma execução iniciada com o código anterior não pode ser retomada com o atual, porque o contrato mudou. E01–E03 se refazem a partir das tags; os resultados arquivados em `outputs/` não mudaram.

**Fase do guia:** F1 (repositório).

---

### 2026-11-02 — Primeiro incremento para ampliar os casos com cobertura funcional

**Sintoma:** 26 das 78 ocorrências permaneciam bloqueadas por lacunas de avaliação funcional.

**Causa:** em CAPTCHA faltava verificar a conta independentemente da resposta retornada; em ZIP faltavam
asserções dos arquivos e bytes extraídos; em campanhas de desconto não havia asserção do valor final
persistido. O ambiente Docker, por si só, não resolve essas lacunas.

**Correção:** três avaliações externas ao alvo, com 16 testes, em `tests/functional/juice_shop/`:
`captcha_arithmetic.test.ts`, `zip_contents.test.ts` e `campaign_discount.test.ts`. A revisão
`config/cobertura_funcional_v2.yaml` e o mapa `config/mapa_testes_relacionados_v3.yaml` incluem os novos
grupos. Os testes do código original passaram; cinco mutações deliberadas foram detectadas como falhas
dos testes esperados, sem falha operacional. O executor de controles restaura apenas os bytes que
escreveu e recusa alterações desconhecidas. Não houve chamadas à LLM.

**Impacto na reprodutibilidade:** a ampliação tem revisão, baseline, imagem e evidências próprios em
`outputs/cobertura_funcional/AMPLIACAO_20261102/`. A revisão v1, o baseline e os resultados da campanha
anterior são preservados. Não se somam medições de campanhas com coberturas distintas sem reconciliação.
O estado final da auditoria e os comandos estão em `docs/cobertura_funcional_v2.md`.

**Fase do guia:** cobertura funcional e validação do critério F.

---

### 2026-11-02 — Segundo incremento: recursos gerados e medidor de startup de server.ts

**Sintoma:** a união por arquivo mantinha 12 casos de `server.ts` bloqueados, mesmo quando a ocorrência
individual já tinha cobertura revisada.

**Causa:** faltavam contratos de parte dos 14 modelos de `autoModels`, seus hooks e o caminho de
erro de `collectDurationPromise`. Testes HTTP normais não comprovam propagação de erro na função de
inicialização.

**Correção:** dois grupos independentes em `server_resources.test.ts` (21 testes de API/banco) e
`server_startup.unit.test.ts` (três testes da função real extraída por AST). Cobrem modelos gerados,
carteira, formatos, exclusão de atributos, associações, paginação, tradução e medição/log/rethrow.
Os 24 testes passaram no código original; os 14 controles da rodada revisada detectaram as regressões
esperadas, sem falha operacional e com restauração dos originais. O controle inicial de paginação
apontava ao teste de usuários, cuja população era menor que o limite de 100; o truncamento já era
detectado pelo teste de dicas, que passou a ser o alvo nominal do controle. A rodada inicial reprovada
foi preservada, sem ser apresentada como resultado final.

**Impacto na reprodutibilidade:** revisão `cobertura_funcional_v3.yaml`, mapa
`mapa_testes_relacionados_v4.yaml` e evidências em `outputs/cobertura_funcional/SERVER_20261102/`.
Revisões anteriores e conjunto D preservados. A função de startup é avaliada isoladamente; não se
alega teste de recuperação de uma inicialização completa. Baseline, auditoria e comandos da revisão
estão em `docs/cobertura_funcional_v3.md`. Nenhuma chamada à LLM nesta ampliação.

**Fase do guia:** cobertura funcional e validação do critério F.

---

### 2026-11-02 — Terceiro incremento: extração dos desafios de código

**Sintoma:** dois casos de `lib/codingChallenges.ts` sem avaliação independente da extração de
marcadores vulneráveis/neutros. Os testes de seleção de respostas não comprovavam esse contrato.

**Causa:** ausência de entradas conhecidas que exercitassem as funções públicas de descoberta e
extração do módulo, inclusive múltiplas chaves e numeração após remoção de linhas ocultas.

**Correção:** grupo `coding_challenges`, com 11 testes do módulo real completo transpilado e executado
com filesystem/logger controlados. Verifica snippets, índices por chave, ocultação, quebras de linha,
comentários `#`, recursão, erros e cache. Os 11 testes passaram e os oito controles de regressão foram
detectados. A primeira validação revelou somente uma comparação de arrays com protótipos distintos
entre contextos; foi ajustada no avaliador, sem alterar o alvo. A evidência inicial foi preservada.

**Impacto na reprodutibilidade:** revisão `cobertura_funcional_v4.yaml`, mapa
`mapa_testes_relacionados_v5.yaml` e evidências em `outputs/cobertura_funcional/CODING_CHALLENGES_20261102/`.
Baselines e conjunto D anteriores preservados. Não se demonstra I/O físico ou segurança de regex por
esses testes F. Baseline, auditoria e comandos em `docs/cobertura_funcional_v4.md`; nenhuma chamada LLM.

**Fase do guia:** cobertura funcional e validação do critério F.

---

### 2026-11-02 — Quarto incremento: seed e autenticação TOTP

**Sintoma:** caso de segredo TOTP em `data/static/users.yml` sem avaliação específica da persistência
do seed e do segundo fator da conta identificada por `timo`.

**Causa:** os testes gerais de login não demonstravam preservação desse vínculo. Fixar o segredo
antigo no avaliador impediria aceitar uma rotação válida.

**Correção:** nove testes independentes de seed, banco e login HTTP em duas etapas, com gerador TOTP
separado do verificador da aplicação e conferido com os vetores SHA1 da RFC 6238. Sete controles
negativos foram detectados. Um controle positivo rotacionou temporariamente o segredo para outra
fixture válida: os mesmos nove testes passaram e o original foi restaurado. Não houve chamada LLM
nem alteração definitiva de credenciais do alvo. Na revisão final, o avaliador passou a exigir as
23 chaves originais de conta, independentemente do YAML candidato; o oitavo controle detectou a perda
de uma chave. A rotação válida continuou passando. As saídas finais têm sufixo `_final`/`_finais`,
preservando a primeira verificação como desenvolvimento.

**Impacto na reprodutibilidade:** revisão `cobertura_funcional_v5.yaml`, mapa
`mapa_testes_relacionados_v6.yaml` e evidências em `outputs/cobertura_funcional/SEED_TOTP_20261102/`.
Revisões e conjunto D anteriores preservados. O controle positivo não é tentativa de remediação;
funcionalidade de login não comprova armazenamento seguro. Método e resultados em
`docs/cobertura_funcional_v5.md`.

**Fase do guia:** cobertura funcional e validação do critério F.

---

### 2026-11-02 — Fechamento dos seis casos restantes do catálogo

**Sintoma:** restavam chat, template de legendas, Grunt e três ocorrências em specs frontend. Um spec
alterado não pode ser a única prova da própria integridade.

**Causa:** faltavam contratos específicos e um avaliador externo dos cenários dos specs candidatos.

**Correção:** cinco grupos, 27 testes externos. O chat executa SDK/banco/SSE reais com transporte
simulado. Legendas executam o JavaScript do Pug real com interfaces de vídeo controladas. Grunt gera
um pacote real de fixture e seus sidecars. Os specs candidatos são executados no Angular, com inventário
completo e sem skips, e precisam detectar mutações temporárias nos métodos reais de produção; um
segundo grupo Angular independente valida guards e renderização. Nenhum adaptador do pipeline foi
alterado nem proteção de avaliador foi desativada.

Os 14 controles negativos detectaram as regressões, inclusive remoção de asserções. Os controles
positivos aceitaram JWTs gerados nos dois specs, SHA-256 com sidecar coerente, separação literal de
legendas e consulta estruturada de avaliações do chat. Os originais foram restaurados. A suíte de
365 testes unitários passou. Nenhuma chamada real a LLM.

**Limitação observada:** o parser original produziu cue sem texto para CRLF na validação inicial.
O grupo final usa VTT/SRT em LF e não declara suporte comprovado a CRLF ou cues iniciados em zero.
O alvo não foi modificado para aprovar o baseline; essa evidência inicial foi preservada. As demais
correções iniciais foram no avaliador: comparação de arrays entre contextos, enumeração de testes e
fixture de cupom compatível com o encoder existente.

**Impacto na reprodutibilidade:** revisão `cobertura_funcional_v6.yaml`, mapa
`mapa_testes_relacionados_v7.yaml` e evidências em `outputs/cobertura_funcional/FINAIS_20261102/`.
JUnit/logs internos ficam em `subavaliacoes/`, com hash do spec candidato. A configuração existente
`execucao_docker_78.yaml` aponta à nova revisão; o modo real original foi preservado e não executado.
Método, baseline e auditoria em `docs/cobertura_funcional_v6.md`. Conjunto D e resultados anteriores
permanecem preservados.

**Fase do guia:** cobertura funcional e validação do critério F.
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
# 02/11/2026 — Cache de respostas e finalização após falha da API

**Sintoma:** o piloto Colab `AMP_REAL_20261017T222912Z_abd18103` registrou HTTP 503,
sem tentativa científica concluída e sem consolidação de métricas. O código também
reutilizava respostas locais por padrão.

**Causa:** falha operacional Colab encerrava a fila; o terminal e o painel só
iniciavam a consolidação após código zero. O cliente OpenAI não repetia timeout
ou conexão interrompida. O piloto sem respostas não tinha `execucoes.jsonl`.

**Correção:** cache local optativo com `LLM_CACHE=desligado` por padrão nos dois
provedores; classificação segura dos erros; retentativas OpenAI limitadas a três
envios e continuidade dos demais pares após falhas não fatais. Colab conserva
reenvio somente para 429. Terminal e painel tentam consolidar dados verificáveis
mesmo após falhas. Eventos operacionais são separados das tentativas científicas.

**Impacto:** relatórios parciais não convertem ausência de resposta em R/F/M=0;
CR mantém o conjunto solicitado. Envios sem uso confirmado têm consumo desconhecido.
Orçamento, autenticação e identidade continuam interrompendo novos envios. O piloto
foi consolidado por leitura em `outputs/resiliencia_llm/RECUPERACAO_PILOTO_20261102_METRICAS/`,
sem modificar a origem. Não houve chamadas reais à LLM nesta validação.

Detalhes, mapa de erros e testes: [feature 09](historico/features/09-resiliencia-llm/README.md).


# 05/11/2026 — Testes que exigem a vulnerabilidade reprovavam correções

**Sintoma:** no piloto de 34 tentativas com os três modelos, 19 removeram o alerta sem criar outro e ainda assim ficaram com F=0. Em 18 delas, os únicos testes reprovados exigiam o próprio comportamento vulnerável, como `bypassSecurityTrustHtml` chamado com `<script>alert("XSS")</script>` e a página de listagem de `/ftp`.

**Causa:** a regra do conjunto D diz que entram os testes cujas asserções só valem com a vulnerabilidade presente, mas as formas (a), (b) e (c) não alcançavam esses testes, e a regra dos mocks os deixava em F. O mesmo ocorria com testes que usam a falha como preparação, como os de feedback que leem o `answer` do CAPTCHA.

**Correção:** critério (d), ligado a casos, em `docs/criterios_conjunto_d.md`. A lista está em `config/conjunto_d_cobertura_v2.json` (41 testes, 20 casos), com a revisão de cobertura v7, o mapa v8 e novo baseline. `conjunto_d.py`, `execucao_cobertura.py`, `camadas.py` e `medicao.py` passaram a informar o caso à classificação.

**Impacto na reprodutibilidade:** a definição de F usada nas execuções muda em relação às campanhas de teste de outubro. Como `camadas.py`, `conjunto_d.py` e `execucao_cobertura.py` são entradas de `docker/referencia.json`, `make docker-check` recusa essas alterações, e a execução passa a usar `docker compose run` direto até uma nova referência. Sem o teste, um patch que apague a funcionalidade inteira de um desses casos deixa de ser reprovado por ele; por isso a conferência manual das correções aceitas é obrigatória na análise.

**Fase do guia:** F4 (validação).

# 06/11/2026 — Campanha completa descartada: testes ainda exigiam a vulnerabilidade

**Sintoma:** a campanha de 78 casos com os três modelos terminou sem erro (41, 36 e 31 casos aceitos), mas correções certas foram reprovadas. O caso mais claro foi a proteção de `PUT /api/Products/:id` reativada pelo GPT-6 Luna e rejeitada pelo teste `PUT update existing product is possible due to Missing Function-Level Access Control vulnerability`.

**Causa:** a separação de 05/11 cobriu os testes vistos no piloto de 3 casos. Dois tipos ficaram de fora: testes que nenhum patch do piloto tinha alcançado e testes mantidos em F de propósito (sandbox breakout, entidades XML). Além disso, a ligação por caso não protegia uma correção que removesse a falha de outro caso.

**Correção:** revisão dos 172 pares de caso e teste reprovados. Critério (e), que vale em todos os casos, ampliação do critério (d), `conjunto_d_cobertura_v3.json`, revisão de cobertura v8, mapa v9 e baseline `IMAGEM_81FE_D3_20261106`. Foi corrigido `server_startup.unit.test.ts`, que exigia a forma concatenada do log, e criado `contratos_legitimos.test.ts`. A opção de inverter o resultado foi rejeitada: qualquer outra falha viraria aprovação. Detalhes em `docs/conjunto_d.md`, seção Versão 3.

**Impacto na reprodutibilidade:** os resultados da campanha de 05 e 06/11 foram descartados pelo grupo e não entram como evidência; a execução dos três modelos foi refeita com chamadas reais. Os critérios mudaram depois de vermos resultados, por isso a mudança vale igual para os três modelos e fica declarada no protocolo. Permanecem sem conclusão as correções que exigem uma variável de ambiente nova para o módulo carregar.

**Fase do guia:** F4 (validação).

# 06/11/2026 — Comparador deixava sem conclusão alertas que só mudaram de linha

**Sintoma:** 89 tentativas da campanha ficaram com `indeterminada_sast`, e 65 delas com F=1. Em 7 tentativas, o alerta alvo saiu e os testes passaram, mas M ficou sem conclusão.

**Causa:** a v2 tratava como ambíguo qualquer alerta sem par, mesmo com a mesma regra, no mesmo arquivo e na mesma quantidade antes e depois. Em 84 das 89 tentativas o motivo foi esse; em nenhuma a contagem caiu com o alvo no grupo. As outras 5 vieram de problema de leitura do arquivo.

**Correção:** `ocorrencias_contexto_v3`, que decide pela contagem da regra no arquivo. Testes em `tests/unit/test_comparacao_v2.py` atualizados; a decisão anterior era não adivinhar pela contagem, e foi revista porque o resultado da tentativa fica rejeitado nos dois sentidos quando o alvo está no grupo.

**Impacto na reprodutibilidade:** o contrato registra o nome do comparador, então execuções v2 não podem ser retomadas com a v3. Um alerta removido e outro igual criado no mesmo arquivo contam como o mesmo; isso está declarado no protocolo.

**Fase do guia:** F4 (validação).

# 06/11/2026 — Teste nosso ainda reprovou a correção oficial de `PUT /api/Products/:id`

**Sintoma:** na campanha final, o GPT-6 Luna (P4, caso `AMP095fcc0f303ff032`) trocou a rota por `security.denyAll()`, que é a correção oficial do Juice Shop, e ficou com R=1, M=1 e F=0.

**Causa:** `creates reads and updates a product through its generated endpoints`, em `tests/functional/juice_shop/server_resources.test.ts`, exige `PUT` autenticado. Ele só apareceu nesta campanha, porque antes a validação parava no teste de `PUT` do Juice Shop.

**Correção:** nenhuma. O grupo decidiu manter o resultado desta campanha, com 49 casos para o GPT-6 Luna. O teste foi conferido sem LLM: reaplicando o patch, só ele falha nos grupos `server_resources` e `server_startup`.

**Impacto na reprodutibilidade:** o GPT-6 Luna fica com um caso a menos do que teria sem esse teste (49 em vez de 50). Foi 1 das 834 tentativas. Os outros modelos corrigiram esse caso com `isAuthorized()`, que o teste aceita.

**Fase do guia:** F4 (validação).

# 06/11/2026 — RRIS: redução medida, mas conjunto sem aprovação nos testes

**Sintoma:** a primeira execução real de `avaliacao_conjunta_rris.py` recusou todos os patches e, corrigido isso, marcou os 49 patches como conflito. Depois de corrigido, a RRIS saiu para os três modelos (GPT-5.6 Luna 70,5%, GPT-6 Luna 60,3%, GPT-4.1 mini 48,7%), mas nenhum conjunto passou em todos os testes.

**Causa:** dois erros do script, que os testes unitários não cobriam: o hash do patch era procurado sem o prefixo `patches/`, e o caminho relativo do patch não valia dentro da worktree. Nos conjuntos, falharam três testes. `POST login newly created user` cria usuário sem `passwordRepeat` e falha só com a correção do caso `AMP8655da69167e4466`. `persists and lists normal feedback through the generated resource` usa o `answer` da resposta e falha só com a correção do caso `AMP4d38adc404310ebe`. Esses dois dependem da falha e ficaram fora do conjunto D porque, testando cada correção sozinha, seus grupos não rodam para esses casos. O terceiro, `keeps every last IP scenario...`, falha só com as correções dos casos `AMP986bde724bde5588` e `AMP417d1da8d7caa6bd` aplicadas juntas, então é uma interação entre elas.

**Correção:** os dois erros do script foram corrigidos e cobertos por testes. O script passou a rodar também os grupos depois da primeira falha, para mostrar o resultado completo. Os três testes não foram alterados: a campanha fica como foi medida, e a RRIS é reportada como redução estática, sem validação funcional do conjunto.

**Impacto na reprodutibilidade:** a evidência está em `outputs/rris/`, sem LLM. Patches em conflito ficam fora do conjunto (9, 8 e 4), por isso a RRIS não é a soma das correções aceitas. A ordem de aplicação é a do início das tentativas e influencia quais patches entram.

**Fase do guia:** F7 (métricas).
