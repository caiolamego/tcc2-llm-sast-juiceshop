# Rodada 7: autorizacao de avaliacoes e promocao Deluxe

Alvo: Juice Shop v20.1.1, commit `f915bddd82790d0f3018902d36ae9b4241a5f51f`,
checkout limpo. Semgrep CE `1.177.0`, mesmas exclusoes, timeout de 30 segundos
por regra/arquivo como no scan completo da rodada 6. Nenhuma LLM executada;
baseline JS001-JS012, scans, triagens e matrizes anteriores preservados.

## Resultado

| Perfil exploratorio acumulado | Alertas brutos | Confirmados | Falsos positivos | Inconclusivos | Desafios distintos confirmados |
|---|---:|---:|---:|---:|---:|
| Ate a rodada 6 | 59 | 41 | 16 | 2 | 35 |
| Ate a rodada 7 | **64** | **43** | **19** | **2** | **37** |

Foram **5 alertas novos, 2 confirmados e 3 falsos positivos**, acrescentando
`forgedReviewChallenge` e `freeDeluxeChallenge`. Os falsos positivos continuam
registrados e nao entram em futuras tentativas de correcao. Nao houve nova
reassociacao de alertas antigos; a revisao SSTI da rodada 6 foi preservada.

| Alerta novo | Resultado da revisao |
|---|---|
| `routes/updateProductReviews.ts:18` | Confirmado: escrita sem verificar autor; `forgedReviewChallenge` |
| `routes/deluxe.ts:43` | Confirmado: modo ausente/desconhecido permite promocao; `freeDeluxeChallenge` |
| `routes/likeProductReviews.ts:36` | Falso positivo para autorizacao por proprietario: outros usuarios podem curtir |
| `routes/likeProductReviews.ts:51` | Falso positivo para autorizacao por proprietario: registro da curtida permitida |
| `routes/orderHistory.ts:36` | Falso positivo: middleware autoriza o papel contabil a atualizar entrega |

O perfil acumulado soma default, custom-rules e rodadas 2 a 7. A matriz
arquiva ainda perfis sobrepostos: sao 95 observacoes, nao 95 falhas distintas.
Mantem 113 desafios unicos e referencias de arquivos/linhas verificadas.

## Avaliacoes: autenticacao nao verifica propriedade

`server.ts:634` exige autenticacao antes de `updateProductReviews`. A rota
obtem o usuario em :16, mas seleciona a escrita somente pelo `_id` recebido
em :18. O autor nao e parte do filtro nem validado antes da escrita; a
comparacao posterior com `user.data.email` apenas registra o desafio.
`data/mongodb.ts` cria uma colecao MarsDB, sem acrescentar escopo de usuario.

A regra `unscoped-document-write` acompanha campos de body/params ate o ID
de update/updateOne com filtro contendo apenas `_id`. Os exemplos protegidos
usam autor/proprietario da identidade autenticada no filtro ou um identificador
derivado da propria identidade. A regra nao entende autorizacao em middleware:
um exemplo com verificacao externa e intencionalmente um alerta esperado,
documentando essa limitacao. Nao se trata de prova automatica de IDOR.

O teste isolado executa o codigo real da rota com usuario diferente do autor,
ID **escalar**, colecao simulada em memoria e hooks dos desafios desativados.
A mensagem e alterada e modified vale 1. Isso distingue a falha de autorizacao
da injecao de operadores NoSQL/multi-update que ja tinha alerta nesse trecho.
E um **novo alerta e novo desafio em local ja conhecido**, nao um novo arquivo
vulneravel; ao selecionar correcoes, as duas causas devem ser coordenadas.

Nos falsos positivos de curtida, nao ha requisito de ser autor da avaliacao.
O codigo verifica usuario e likedBy antes de atualizar. Ha um caminho de
concorrencia a investigar separadamente, mas estes alertas **nao** confirmam
`timingAttackChallenge` apenas por ocorrerem no mesmo arquivo.

Em `orderHistory.ts`, `server.ts:625` aplica `isAccounting`, que verifica
papel em `lib/insecurity.ts:154-162`; uma operacao contabil nao exige que o
pedido seja do proprio operador. Os testes oficiais de order-history foram
consultados como evidencia adicional, nao executados nesta rodada.

## Deluxe: modo desconhecido pula as precondicoes

Em `routes/deluxe.ts`, dois ifs independentes tratam wallet e card. Um modo
ausente, null ou diferente de ambos nao entra em nenhum deles, mas chega a
`user.update` que muda role em :43. `server.ts:629` usa appendUserId para
vincular a conta autenticada; esse middleware nao valida paymentMode. O
problema nao e promocao anonima de qualquer conta.

A regra `optional-mode-role-update` relaciona dois modos distintos do mesmo
campo de requisicao em ifs independentes e a atualizacao posterior de role.
Os exemplos negativos incluem rejeicao explicita de modos desconhecidos,
if/else-if com else de rejeicao e atualizacao sem mudanca de role. Os nomes
de campos, valores de modo e papeis nos exemplos diferem dos do Juice Shop.
Controles em outro middleware ou guardas com outra sintaxe ainda podem gerar
falsos positivos: a regra e candidata de auditoria, nao analise completa de
todos os caminhos de execucao.

Os testes isolados do codigo real da rota reproduzem promocao com modo
ausente, null e desconhecido, sem consultar carteira/cartao nem debitar saldo.
Controles verificam que wallet valido debita, saldo insuficiente bloqueia e
cartao inexistente bloqueia. O teste Cypress oficial de Deluxe documenta
requisicao sem paymentMode; foi lido, nao executado.

## Validacao e limites metodologicos

- Testes positivos/negativos das 17 regras passaram.
- 32 testes Python passaram, incluindo preservacao dos alertas antigos,
  do baseline e da proveniencia SSTI.
- 7 testes isolados de rotas passaram com Node `v24.14.0`.
- Scan novo sem avisos; manifesto registra versao, exclusoes, timeout e hashes.
- Repeticao em diretorio temporario retornou os mesmos cinco alertas
  (regra, arquivo e intervalo), novamente sem avisos.

`tests/integration/rodada7/test.mjs` le os dois arquivos do checkout fixado,
remove imports/exports para injetar dependencias simuladas e remove tipos
TypeScript com Node. As funcoes das rotas nao sao reimplementadas. O script
exige commit correto e checkout limpo. Nao sobe servidor, nao usa rede, nao
carrega codefixes e nao faz cobranca real. Node emite aviso de API experimental
para stripTypeScriptTypes; a versao usada esta explicitada acima.

Esses testes exercitam a logica das rotas com mocks: **nao substituem testes
HTTP com autenticacao/banco reais**, nem validacao de futuros patches da LLM.
As regras foram criadas apos inspecao do alvo; a cobertura e exploratoria,
nao uma avaliacao cega de capacidade de generalizacao do Semgrep. O numero de
desafios nao equivale a numero de causas independentes nem a recall de SAST
sobre todos os 113 desafios.

## Artefatos e reproducao

Triagem em `config/auditoria_desafios_rodada7.yaml`; scan e manifesto em
`outputs/auditoria_sast/rodada7.json` e `manifesto-rodada7.json`; matriz JSON,
CSV e resumo em `outputs/auditoria_sast/rodada7/`.

Use Semgrep 1.177.0 no PATH ou `--semgrep-bin`. Para o teste de rotas, use Node
24.14.0. Os caminhos abaixo pressupõem o checkout limpo em /tmp.

```bash
semgrep scan --test rules --metrics=off
JUICE_SHOP_WORKTREE=/tmp/tcc-juiceshop-audit node --test tests/integration/rodada7/test.mjs
python3 scripts/audit/scan_semgrep_exploratorio.py \
  --worktree /tmp/tcc-juiceshop-audit --perfis rodada7 --timeout 30 \
  --saida "$(mktemp -d /tmp/tcc-semgrep-rodada7-XXXXXX)"
python3 scripts/audit/build_challenge_matrix.py \
  --worktree /tmp/tcc-juiceshop-audit \
  --scan-extra rodada2=outputs/auditoria_sast/rodada2.json \
  --scan-extra rodada3=outputs/auditoria_sast/rodada3.json \
  --scan-extra rodada4=outputs/auditoria_sast/rodada4.json \
  --scan-extra rodada5=outputs/auditoria_sast/rodada5.json \
  --scan-extra rodada6=outputs/auditoria_sast/rodada6/scan_completo/rodada6.json \
  --scan-extra rodada7=outputs/auditoria_sast/rodada7.json \
  --triagem-extra config/auditoria_desafios_rodada2.yaml \
  --triagem-extra config/auditoria_desafios_rodada3.yaml \
  --triagem-extra config/auditoria_desafios_rodada4.yaml \
  --triagem-extra config/auditoria_desafios_rodada5.yaml \
  --triagem-extra config/auditoria_desafios_rodada6.yaml \
  --triagem-extra config/auditoria_desafios_rodada7.yaml \
  --revisoes config/revisoes_associacoes_rodada6.yaml \
  --saida outputs/auditoria_sast/rodada7
python3 scripts/reports/report_rodada7.py
python3 -m unittest discover -s tests/unit -p 'test_*.py'
```

## Pendencias

Os proximos candidatos continuam sendo a selecao de pedidos por email
anonimizado (`dataExportChallenge`) e quantidade negativa na cesta
(`negativeOrderChallenge`), com as verificacoes descritas na rodada 6.
Nao estao incluidos nestes 37 desafios confirmados.

O catalogo antigo `candidatos_correcao.csv` permanece com 16 causas/20 desafios.
Ainda e preciso preparar uma selecao ampliada por causa, evitar contar duas
regras no mesmo trecho como dois casos independentes e definir testes de
seguranca/regressao antes da execucao da LLM pelo usuario.
