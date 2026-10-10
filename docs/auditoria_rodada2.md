# Segunda rodada exploratoria de regras Semgrep

Alvo: Juice Shop v20.1.1, commit `f915bddd82790d0f3018902d36ae9b4241a5f51f`.
Semgrep CE `1.177.0`; mesmas exclusoes de `config/semgrepignore`. Esta
rodada **nao alterou** o baseline JS001-JS012, os JSONs anteriores nem a
execucao da LLM. Os resultados estao em
`outputs/auditoria_sast/rodada2.json`, `manifesto-rodada2.json` e
`outputs/auditoria_sast/rodada2/`.

## Resultado

| Conjunto | Alertas brutos | Confirmados | Falsos positivos | Inconclusivos | Desafios distintos confirmados |
|---|---:|---:|---:|---:|---:|
| `p/default` + tres regras locais anteriores | 40 | 26 | 13 | 1 | 20 |
| Novas duas regras isoladas | 4 | 3 | 1 | 0 | 2 novos |
| Perfil exploratorio ampliado | **44** | **29** | **14** | **1** | **22** |

Os quatro novos alertas sao: `lib/insecurity.ts:41` (MD5 usado pela senha),
`server.ts:676,729` (duas inscricoes da mesma rota publica `/metrics`) e
`Gruntfile.js:75` (MD5 usado para checksum). Os tres primeiros foram confirmados
na triagem; o ultimo e falso positivo **para armazenamento de senhas**, pois
calcula checksum dos artefatos de distribuicao. As duas linhas de `/metrics`
representam **um** desafio, nao duas falhas independentes. A nova matriz
mantem 113 desafios; `weakPasswordChallenge` e `exposedMetricsChallenge`
passaram de pendentes a confirmados. A soma de todos os scans arquivados,
incluindo perfis sobrepostos, e 75 observacoes; **nao** e o numero de alertas
do perfil ampliado, que e 44.

`weakPasswordChallenge`: `models/user.ts:76` chama `security.hash` para o
campo `password`; a funcao em `lib/insecurity.ts:41` usa `createHash('md5')`
sem salt. O alerta cai fora do marcador do desafio e foi vinculado por revisao
manual entre arquivos. A regra e generica e pode alertar usos nao relacionados
a senhas, como ocorreu no `Gruntfile.js`.

`exposedMetricsChallenge`: `server.ts` registra `/metrics` sem middleware de
autorizacao em duas posicoes; `routes/metrics.ts` devolve
`register.metrics()` sem checar identidade. O teste existente
`test/api/metrics.test.ts` espera HTTP 200 para GET anonimo e marca o desafio
como resolvido. A regra sinaliza rota de metricas sem middleware **explicito**;
um handler que autentique internamente ainda exigiria triagem manual.

O scan novo registrou um aviso de timeout de parsing para
`frontend/src/assets/private/three.js`. Portanto, cobertura perfeita do
codigo escaneado nao deve ser presumida.
Uma repeticao em diretorio temporario encontrou os mesmos quatro triplos
`(regra, arquivo, linha)` e o mesmo aviso. O SHA do JSON completo variou
porque o campo de tempos de execucao (`time`) varia; os achados nao variaram.

## Desafios investigados sem regra promovida

- `forgedReviewChallenge`: `server.ts:634` exige usuario autenticado, mas
  `routes/updateProductReviews.ts:17-21` seleciona so `_id` vindo do corpo e
  nao inclui o autor autenticado no filtro nem o compara antes da escrita.
  `test/cypress/e2e/noSql.spec.ts` demonstra edicao de avaliacao alheia.
  Uma regra que apenas encontre `update({_id: req.body.id}, ...)` tambem
  acusaria codigo seguro que verifica o proprietario antes da chamada; a
  regra MongoDB anterior confirma somente `noSqlReviewsChallenge`. Por isso,
  `forgedReviewChallenge` continua sem **alerta SAST confirmado**, embora a
  vulnerabilidade seja conhecida.
- `registerAdminChallenge`: `server.ts:487,504` publica `User` via Finale e
  exclui `password` e `totpSecret`, mas nao `role`. O middleware em
  `routes/verify.ts:51-56` so registra o desafio e chama `next()`; o modelo
  permite `admin`. `test/api/user.test.ts` espera status 201 e papel `admin`
  ao cadastrar usuario anonimamente. Uma regra baseada apenas na ausencia de
  `role` em `excludeAttributes` acusaria recursos protegidos por middleware ou
  configuracao em outro arquivo. Sem regra que diferencie esses casos nos
  testes, o desafio nao e contado como novo alerta.

Essas duas decisoes evitam usar nomes de desafios ou numeros de linha como
condicoes das regras e evitam confundir ausencia de alerta com ausencia de
vulnerabilidade.

## Reproduzir

As regras e fixtures estao em `rules/rodada2/`. Para verificar e repetir sem
sobrescrever os JSONs historicos:

```bash
semgrep scan --test rules/rodada2 --metrics=off
python3 scripts/scan_semgrep_exploratorio.py \
  --worktree /tmp/tcc-juiceshop-audit --perfis rodada2 \
  --saida /tmp/semgrep-rodada2-repeticao
python3 scripts/build_challenge_matrix.py \
  --worktree /tmp/tcc-juiceshop-audit \
  --scan-extra rodada2=outputs/auditoria_sast/rodada2.json \
  --triagem-extra config/auditoria_desafios_rodada2.yaml \
  --saida outputs/auditoria_sast/rodada2
python3 scripts/report_rodada2.py
python3 -m unittest discover -s scripts -p 'test_report_rodada2.py'
```

No comando de repeticao, forneca o binario Semgrep `1.177.0` caso o `semgrep`
do PATH tenha outra versao. A matriz e o resumo gerados podem ser reconstruidos;
os artefatos historicos ficam preservados. O catalogo de candidatos a correcao
com 16 causas/20 desafios pertence a rodada anterior e **nao** foi atualizado
automaticamente para incluir os dois novos desafios.
