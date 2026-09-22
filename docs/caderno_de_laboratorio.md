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

Um segundo erro apareceu ao tentar `npm install` manualmente como workaround: falhou por ter sido executado na raiz do repositório do TCC (onde não há `package.json` de aplicação), e não dentro do worktree do alvo (`workspace/wt-01`).

**Correção:** `scripts/setup_target.sh` alterado de `npm ci --no-audit --no-fund` para `npm install --no-audit --no-fund`. O comando roda dentro da subshell `( cd "$WT" && ... )`, então, executado via script, sempre acontece no diretório correto — o segundo erro só ocorre se o comando for repetido manualmente fora do script.

**Impacto na reprodutibilidade:** sim. Sem lockfile versionado, `npm install` resolve as versões de dependências de acordo com os ranges (`^`, `~`) do `package.json` no momento da execução — o conjunto de versões instalado pode divergir entre execuções feitas em datas diferentes, ou entre as máquinas dos dois integrantes do grupo.

Precisa constar na seção de Limitações do TCC 2 como fonte de não determinismo do **ambiente**, separada e adicional ao não determinismo já discutido da LLM.

**Mitigação possível (não aplicada ainda):** após a primeira instalação bem-sucedida, copiar o `package-lock.json` efetivamente gerado em `workspace/wt-01/package-lock.json` para `config/package-lock.snapshot.json`, versionado no repositório do TCC, como registro exato das versões usadas no experimento. Isso não restaura o comportamento do `npm ci` (ainda seria preciso `npm install` para reinstalar), mas documenta com precisão o que foi usado, para efeito de reprodutibilidade e de citação na monografia.

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

**Correção de acompanhamento (mesmo dia):** a decisão de `TZ=UTC` tinha sido registrada aqui e no guia, mas não tinha sido de fato aplicada em `scripts/measure_validation_cost.py` — o script continuou chamando os comandos sem a variável. Confirmado numa segunda execução em `workspace/wt-1`: T3 falhou de novo com o mesmo erro de fuso horário, e T4 já mostrava só a falha de rede isolada (confirmando que a correção do conflito de porta, essa sim, funcionou). Corrigido adicionando `os.environ["TZ"] = "UTC"` logo após os imports do script, antes de qualquer `subprocess.run`/`Popen` — processos filhos herdam o ambiente do pai, então isso basta para propagar a variável para `npm`, `npx` e `node` sem precisar alterar cada chamada individualmente. Confirmado numa terceira execução, já em `workspace/wt-1` com a correção aplicada: T3_suite_unitaria passou em 1.9s, 0 falhas — a correção de `TZ=UTC` embutida no script fecha de ponta a ponta, não só manualmente. (T4_api reprova na mesma execução, em 13.0s, pela falha de rede externa já registrada no item 2 — sem relação com fuso horário.)

**Fase do guia:** F2.4 → decisão nova incorporada a D6 e ao escopo de F4.

---

<!--
Próxima entrada:

### AAAA-MM-DD — título curto

**Sintoma:** o que foi observado
**Causa:** diagnóstico
**Correção:** o que foi mudado
**Impacto na reprodutibilidade:** sim/não — se sim, por quê
**Fase do guia:** referência (ex.: F2.2)
-->

============================================================
Resumo -- cole isto no caderno de laboratorio (F2.4):

T0_compilacao: 1.5s (passou)
T2_arquivo_unico: 0.2s (passou)
T3_suite_unitaria: 1.9s (passou)
T4_api: 13.0s (FALHOU)
T5_desafio_cypress: 7.3s (passou)