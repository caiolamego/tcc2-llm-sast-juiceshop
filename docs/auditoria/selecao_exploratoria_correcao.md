# Selecao exploratoria para uma eventual segunda rodada de correcoes

Esta selecao **nao substitui** o baseline JS001-JS012 nem autoriza misturar
resultados das duas rodadas. Ela usa a matriz de 113 desafios do Juice Shop
v20.1.1 (`f915bddd82790d0f3018902d36ae9b4241a5f51f`) e os scans ja
arquivados. O gerador e a especificacao revisavel estao em
`scripts/audit/build_repair_candidates.py` e
`config/candidatos_correcao_exploratorios.yaml`; os resultados estao em
`outputs/auditoria_sast/candidatos_correcao.{json,csv}`.

## Decisao provisoria

`p/default` + as tres regras locais e o perfil candidato escolhido nesta
auditoria. Ele cobre os 20 desafios associados a alertas confirmados; a regra
local de redirecionamento aponta melhor a causa, embora o alerta generico de
`p/default` ja cubra esse desafio. Sao
**16 causas/possiveis unidades de patch**, nao 20 correcoes independentes:
um SQL injection na autenticacao corresponde a tres desafios; a busca a dois;
o XSS do parametro `q` a dois. Os alertas de `p/security-audit` nao acrescentam
desafio confirmado a essa uniao. A escolha e exploratoria e foi feita **depois
de examinar o alvo**; nao mede recall independente do Semgrep sobre os 113.

Os 16 grupos usam so alertas confirmados. Falsos positivos continuam na matriz
e no JSON de scan, com justificativa, mas nao viram tentativas de correcao.
Achados confirmados sem associacao a desafio (segredos em `users.yml`, chaves
em `lib/insecurity.ts` e listagem de chaves) ficam fora desta coorte, sem serem
negados como falhas. O alerta inconclusivo de `quarantineServer.ts` tambem fica
fora. O desafio `forgedReviewChallenge` nao foi incluido: o alerta MongoDB
comprova o mecanismo de `noSqlReviewsChallenge`, nao toda a falha de
autorizacao do outro desafio.

Quatro grupos estao marcados como **piloto metodologico**: EXP001 (SQL no login),
EXP007 (redirecionamento), EXP008 (MongoDB) e EXP010 (XSS do parametro `q`).
Isso e prioridade de preparacao, **nao** selecao final nem permissao para rodar
a LLM. Os outros doze permanecem como candidatos posteriores.

## Barreiras antes de executar a LLM

1. Congelar as definicoes remotas usadas de `p/default` ou trocar por um
   arquivo local versionado e comprovar que o scan reproduz os alertas.
   Arquivar hash das regras, versao do Semgrep, comando, exclusoes e resultado.
   Os JSONs de hoje fixam a observacao passada, nao o comportamento de um
   re-scan futuro.
2. Criar **testes de regressao de seguranca que falhem no codigo vulneravel e
   passem no corrigido** para cada grupo escolhido. Testes oficiais do Juice
   Shop frequentemente fazem o inverso: verificam que a exploracao *resolve*
   o desafio. Exemplo: `test/server/redirect.unit.test.ts` aceita a URL que
   engana a allowlist; `test/cypress/e2e/publicFtp.spec.ts` espera acesso com
   null byte; `test/api/product.test.ts` espera descricao XSS inalterada.
   Eles sao evidencias do defeito e podem falhar legitimamente apos o reparo;
   nao sao oraculos de seguranca pos-correcao.
3. Definir o criterio R por **ocorrencia/causa**, com comparacao resistente a
   deslocamento de linhas, e medir o teste de seguranca separadamente. O R
   atual usa `(check_id, path)`. Ha tres colisoes entre grupos: EXP003/004 em
   `server.ts`, EXP009/010 em `search-result.component.ts`, EXP011/012 em
   `administration.component.ts`. Corrigir so um deles pode deixar o mesmo par
   regra/arquivo ativo, dando R=0 mesmo para um reparo valido. Numero de linha
   fixo nao serve como identidade apos um patch; uma ancora semantica e revisao
   do diff sao necessarias. **R=1 sozinho nunca comprova seguranca**.
4. Definir no novo protocolo a unidade de amostragem (grupo EXP, e nao
   desafio), filtros, triagem, conjunto de testes e tratamento de testes
   oficiais que deliberadamente esperam a vulnerabilidade. Se o caso MongoDB
   entrar no experimento principal, acrescentar CWE-943 ao mapa de categorias
   ou registrar explicitamente que ele usa a categoria generica `OUTRO`.

Testes de regressao propostos para o piloto, ainda **nao implementados**:

| Grupo | Prova negativa no alvo vulneravel | Resultado exigido apos o patch |
|---|---|---|
| EXP001 | Email com metacaracteres SQL altera a clausula da consulta | Login nao autentica com payload e login legitimo continua funcionando |
| EXP007 | URL externa contendo URL permitida como substring e aceita | Rejeita host externo e preserva URL realmente permitida |
| EXP008 | Seletor `_id` em objeto e `multi: true` podem afetar avaliacoes fora do alvo | Aceita so ID escalar autorizado e altera no maximo uma avaliacao |
| EXP010 | `q` controlado pelo usuario chega a `bypassSecurityTrustHtml` | Payload aparece como texto inerte, busca normal continua funcionando |

No EXP008, um teste somente de tipo de ID pode nao capturar autorizacao; essa
e uma verificacao **distinta** de `forgedReviewChallenge` e nao deve ser
contada como coberta pelo alerta atual. No EXP010, um teste de componente
Angular ou navegador e necessario: a suite T0/T3/T4 existente nao prova que
o HTML renderizado ficou seguro.

## Reproduzir a selecao

```bash
python3 scripts/audit/build_repair_candidates.py
python3 -m unittest discover -s tests/unit -p 'test_repair_candidates.py'
```

O gerador falha se houver desafio repetido, alerta falso positivo selecionado,
vinculo sem confirmacao, ou se algum dos 20 desafios confirmados pela dupla de
perfis ficar sem grupo. Isso verifica a **consistencia da selecao**, nao a
seguranca dos futuros patches.
