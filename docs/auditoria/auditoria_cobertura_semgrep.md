# Auditoria exploratória de cobertura do Semgrep

Data: 2026-10-10. Alvo: OWASP Juice Shop v20.1.1, commit
`f915bddd82790d0f3018902d36ae9b4241a5f51f`. Semgrep CE `1.177.0`.

Esta auditoria responde à dúvida sobre os 12 itens do catálogo. Ela **não** muda
`outputs/sast_antes/`, os IDs JS001–JS012 nem o protocolo da execução principal.
As regras do registro do Semgrep não estão congeladas; uma repetição futura pode
dar outro resultado mesmo com a mesma versão do programa. Por isso, os JSONs e o
manifesto de cada scan são guardados em `outputs/auditoria_sast/`.

## Resultados medidos

| Configuração | Ocorrências brutas | Pares regra/arquivo | Locais distintos | Avisos de parsing |
|---|---:|---:|---:|---:|
| Baseline arquivado, 5 rulesets | 15 | 12 | 13 | 8 |
| Reexecução dos mesmos 5 rulesets | 15 | 12 | 13 | 11 |
| `p/default` | 29 | 22 | 28 | 9 |
| `p/security-audit` | 7 | 6 | 7 | 2 |
| Regra local genérica para Angular | 9 | 7 | 9 | 0 |
| Três regras locais combinadas | 11 | 9 | 11 | 0 |

A reexecução dos cinco rulesets encontrou exatamente os mesmos 15 triplos
`(regra, arquivo, linha)` do baseline arquivado. As diferenças na quantidade de
arquivos escaneados e de avisos mostram que o ambiente de origem não foi
reproduzido integralmente; a comparação de findings, porém, é exata.
Na reexecução de 10/10, `p/default` manteve os 29 alertas mas passou de 11 para
9 avisos; regras remotas e condições de parsing não estão congeladas. Os JSONs
e seus hashes na matriz são a referência exata para esta rodada.

`p/default` encontrou 15 **locais** que não estavam no baseline. Três ficam em
arquivos `.spec.ts` (testes), e um alerta `INFO` não passaria pelo filtro de
severidade vigente. Entre os demais há candidatos em `routes/captcha.ts`,
`routes/currentUser.ts`, `routes/videoHandler.ts`,
`views/promotionVideo.pug` e `lib/insecurity.ts`. Também aparecem um segredo
em `data/static/users.yml` e código do instrutor de hacking; a elegibilidade
dessas áreas precisa ser definida antes de gerar um novo catálogo.
O conjunto `p/default` também cobre todos os 13 locais distintos do baseline;
ele deixa de emitir duas regras de SQL Injection que apontavam para locais já
apontados por outra regra. Assim, substituir os cinco rulesets por `p/default`
não perdeu locais neste commit, embora mude os IDs e a composição das regras.

`p/security-audit` encontrou cinco locais novos: três em templates e dois em
`routes/videoHandler.ts`. A linha 57 de `videoHandler.ts` contém uma *string
literal de ataque usada para reconhecer o desafio*, não a inserção do dado no
HTML. Já a linha 71 concatena `subs` dentro de uma tag `<script>`; é um
candidato concreto para análise. O aviso nos templates sobre atributo sem aspas
precisa ser avaliado à luz do escaping do Angular/Handlebars. Portanto, contar
todos esses avisos como vulnerabilidades confirmadas seria incorreto.
Os dois locais de `videoHandler.ts` também aparecem em `p/default`; portanto,
ao combinar os perfis, `p/security-audit` acrescenta apenas os três avisos de
template.

Triagem pontual de `p/default`: `routes/currentUser.ts:31` copia para a resposta
um campo escolhido pela query do cliente e merece investigação de exposição de
dados. `routes/captcha.ts:22` usa `eval`, mas a expressão é construída apenas
com números aleatórios e três operadores fixos; o alerta não prova injeção
controlada por usuário. Em `views/promotionVideo.pug:75`, a regra de XSS
confundiu o operador JavaScript `!=` com sintaxe de interpolação Pug `!=`:
este é um falso positivo evidente. Esses exemplos mostram por que o total bruto
não pode ser usado diretamente como denominador de vulnerabilidades reais.

A regra local `rules/rodada1/angular-sanitizer-bypass.yaml` sinaliza usos da API
`bypassSecurityTrustHtml`, independentemente da origem do valor. Encontrou nove
ocorrências em sete arquivos, inclusive os pontos marcados no Juice Shop para
`restfulXssChallenge` e `localXssChallenge` em
`frontend/src/app/search-result/search-result.component.ts:110,143`.
Uma chamada a essa API é uma *possível* falha: o valor pode ser controlado por
usuário, vir de dados confiáveis ou já ter sido sanitizado. A regra foi escrita
**depois** da inspeção do alvo e deve ser apresentada como análise exploratória,
não como detector independente usado para estimar a sensibilidade inicial.

As duas regras adicionais apontaram `routes/updateProductReviews.ts:17-21`
(selector `_id` vindo de `req.body` com `multi: true`) e
`lib/insecurity.ts:135-137` (URL aceita por substring da allowlist). A primeira
confirma o mecanismo de `noSqlReviewsChallenge`, **não** prova sozinha a falha de
autorização de `forgedReviewChallenge`. A segunda confirma o mecanismo de
`redirectChallenge`. As soluções oficiais dos Coding Challenges foram usadas
somente para conferir esta interpretação, não no scan nem em prompts.

A matriz em `outputs/auditoria_sast/matriz_desafios.{json,csv}` cruza os 113
desafios com marcadores, alertas brutos e triagem manual. Ela classifica 25 como
candidatos a SAST pelo marcador em código JS/TS, 3 como fora do escopo JS/TS
(Solidity), 8 como candidatos identificados por revisão manual **sem marcador**
e 77 como indeterminados *com a evidência disponível*, não como vulnerabilidades
ausentes. Dos 71 alertas acumulados entre cinco scans (com repetições entre
perfis), 49 ocorrências foram confirmadas, 20 classificadas como falsos
positivos e 2 como inconclusivas. Isso equivale a 29, 16 e 1 combinações
distintas `(regra, arquivo, linha)`, respectivamente. Não há alertas sem
revisão nesta rodada.

Os alertas confirmados correspondem a **20 desafios distintos** na união dos
scans: 10 já apontados pelo baseline e 10 adicionais. A
contagem anterior de 7 desafios no baseline considerava apenas a coincidência
com linhas marcadas. A revisão manual também ligou alertas antigos de
`routes/redirect.ts`, `routes/userProfile.ts` e `routes/fileServer.ts` a desafios
que não têm marcador naquele local. As novas regras MongoDB e redirecionamento adicionaram um desafio
exclusivo em relação ao baseline (`noSqlReviewsChallenge`); o redirecionamento
já tinha um alerta genérico no baseline, mas a regra nova aponta a **causa** do
defeito na allowlist. Isto é cobertura de desafios confirmados neste conjunto,
não recall sobre todas as 113 vulnerabilidades.

### Revisão dos alertas pendentes

A revisão das 34 combinações `(regra, arquivo, linha)` que estavam pendentes
usou o fluxo de dados no código da versão fixada e os mecanismos descritos no
catálogo do Juice Shop. As decisões individuais e os motivos estão em
`config/auditoria_desafios.yaml`; a matriz materializa o resultado. Para
desafios sem marcador no arquivo alertado, a associação aparece explicitamente
como `confirmacao_manual_sem_marcador`, não como acerto automático de linha.

Exemplos de confirmações: `routes/currentUser.ts:31` permite pedir o campo
`password` pela query `fields`; `frontend/src/app/last-login-ip/last-login-ip.component.ts:39`
exibe como HTML confiável o IP que pode vir do header `true-client-ip` quando o
desafio está ativo; `frontend/src/app/track-result/track-result.component.ts:48`
exibe o ID retornado pela API como HTML confiável. O aviso em
`routes/videoHandler.ts:71` aponta a concatenação de legendas dentro de uma tag
`script`; a exploração depende de controlar o arquivo de legendas. Uso de
`bypassSecurityTrustHtml` só foi confirmado quando a origem não confiável foi
demonstrada. A documentação do Angular confirma que a API desliga sua proteção
normal de sanitização: https://angular.dev/best-practices/security .

Exemplos de falsos positivos: os três JWTs em arquivos `.spec.ts` são tokens de
teste; `routes/videoHandler.ts:57` contém apenas a string usada pelo verificador
do desafio; `frontend/src/app/navbar/navbar.component.html:17` e
`purchase-basket.component.html:15` usam interpolação do Angular em atributos,
tratada como binding seguro, não concatenação de HTML cru. A documentação do
Angular descreve esse comportamento: https://angular.dev/guide/templates/class-binding .

Uma segunda revisão com testes dirigidos resolveu cinco dos seis locais antes
inconclusivos:

- O payload de `test/server/insecurity.unit.test.ts` para feedback,
  ``<<script>Foo</script>iframe src="javascript:alert(`xss`)">``, passou por
  `sanitize-html@1.4.2` como o iframe perigoso em um teste isolado; tanto a
  página About quanto a administrativa desativam a sanitização Angular do
  comentário persistido. Os dois alertas foram ligados manualmente a
  `persistedXssFeedbackChallenge`.
- Em teste HTTP local com `express@4.22.1`, a rota equivalente a
  `routes/fileServer.ts` respondeu **200** para
  `package.json.bak%2500.md` e serviu `ftp/package.json.bak`; o mesmo nome sem
  `%2500.md` recebeu **403**. A checagem de extensão acontece antes de remover
  `%00`. O alerta foi ligado a `nullByteChallenge`, **não** a traversal fora de
  `ftp`.
- A listagem de `.well-known` expõe apenas `security.txt`, não um diretório
  sensível; foi marcada falso positivo para a finalidade desta auditoria.
- Para `views/dataErasureForm.hbs:38`, um teste isolado com
  `handlebars@4.7.7` e parser HTML confirmou que `=` é escapado e o payload
  `x onfocus=alert(1) autofocus` não cria atributo executável. O aviso de XSS
  foi marcado falso positivo; o atributo sem aspas pode alterar atributos
  booleanos e merece correção de estilo, mas não confirma CWE-79.

Resta **um local inconclusivo**, `routes/quarantineServer.ts:14` (duas
ocorrências entre perfis): a rota serve arquivos da quarentena publicamente,
mas a checagem de barra impede o traversal simples que a regra genérica sugere.
Sem demonstrar impacto de um arquivo específico, ele não entra na amostra de
correção. `res.sendFile` pode expor arquivos se o caminho vindo do usuário não
for restringido, mas a simples chamada não prova traversal; ver
https://expressjs.com/en/4x/api/response/ .

## Interpretação metodológica

Os 113 desafios declarados pelo Juice Shop não são 113 unidades de código
independentes. O Semgrep CE também tem falsos negativos, falsos positivos e
limitações para fluxo entre funções e arquivos. O baseline informou oito avisos
de parsing parcial em templates Angular, que precisam constar das limitações.

O agrupamento atual por `(check_id, path)` reduz quatro ocorrências da regra
de listagem de diretório em `server.ts` a um caso. É uma unidade de análise
válida se declarada, mas o número 12 não é o número de locais detectados.

Para mudar o conjunto principal, a decisão deve vir **antes de olhar os
resultados das correções pela LLM**: definir rulesets, caminhos, severidade,
unidade de deduplicação, triagem de falsos positivos e correspondência com
testes. Em seguida, regenerar baseline, catálogo e IDs e executar todo o
experimento com o conjunto congelado. Nunca misturar tentativas feitas com
regras diferentes na mesma tabela de TRV.

Uma opção prática é usar `p/default` como novo candidato de baseline, pois ele
achou mais locais no código da aplicação. A regra Angular pode entrar como
extensão exploratória separada, com sua precisão avaliada manualmente. Ainda não
há evidência de que trocar de SAST seja necessário; primeiro é preciso medir
quantos dos novos alertas são elegíveis, distintos e validáveis.

## Como reproduzir

Com Semgrep `1.177.0` instalado e um worktree limpo no commit acima:

```bash
python3 scripts/audit/scan_semgrep_exploratorio.py --worktree workspace/wt-1
python3 scripts/audit/audit_semgrep_coverage.py \
  outputs/sast_antes/baseline_raw.json \
  outputs/auditoria_sast/default.json \
  outputs/auditoria_sast/security-audit.json \
  outputs/auditoria_sast/angular-sanitizer-bypass.json \
  outputs/auditoria_sast/custom-rules.json
semgrep scan --test rules
python3 -m unittest discover -s tests/unit -p 'test_challenge_matrix.py'
python3 scripts/audit/build_challenge_matrix.py --worktree workspace/wt-1
```

O script verifica o commit antes de iniciar e reaproveita as exclusões de
`config/semgrepignore`. Os arquivos de auditoria são independentes do catálogo.
