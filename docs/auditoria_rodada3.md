# Terceira rodada delimitada de cobertura Semgrep

Alvo: Juice Shop v20.1.1, commit `f915bddd82790d0f3018902d36ae9b4241a5f51f`;
Semgrep CE `1.177.0`, mesmas exclusoes de `config/semgrepignore`. Os scans
historicos, o baseline JS001-JS012 e os resultados da LLM nao foram alterados.

## Resultado medido

| Perfil exploratorio | Alertas brutos | Confirmados | Falsos positivos | Inconclusivos | Desafios distintos confirmados |
|---|---:|---:|---:|---:|---:|
| `p/default` + regras locais anteriores + rodada 2 | 44 | 29 | 14 | 1 | 22 |
| Nova regra isolada | 1 | 1 | 0 | 0 | 1 novo |
| Perfil acumulado | **45** | **30** | **14** | **1** | **23** |

A regra `tcc.express.security.trust-all-proxies-rate-limit` encontrou
`server.ts:342-347`, sobrepondo a linha vulneravel 346 marcada para
`resetPasswordMortyChallenge`. O servidor chama `app.enable('trust proxy')`
e usa um valor derivado do header/IP do pedido para a chave do rate limiter
da redefinicao de senha. A [documentacao oficial do Express](https://expressjs.com/en/guide/behind-proxies/)
explica que `trust proxy: true` aceita `X-Forwarded-For` e exige que o proxy
de borda remova ou sobrescreva o header; caso contrario, o cliente pode
escolher o IP visto pela aplicacao. A associacao com o desafio e confirmada
no codigo fixado, **com a premissa de que o proxy de borda nao neutraliza o
header**. O alerta e de baixa confianca para outros deployments e requer
triagem manual. Ele nao comprova exploracao em toda instalacao do Juice Shop.

O novo scan tem uma ocorrencia e zero avisos de parsing. A matriz da rodada 3
contem 113 desafios e 76 observacoes somadas entre **todos** os scans
arquivados, inclusive perfis sobrepostos. Esse 76 nao e o numero de alertas
do perfil acumulado (45). O resumo reproduzivel esta em
`outputs/auditoria_sast/rodada3/resumo.json`.

## Os dez desafios com marcador ainda sem alerta confirmado

| Desafio(s) | Motivo para nao promover uma regra nesta rodada |
|---|---|
| `registerAdminChallenge`, `forgedReviewChallenge` | Falhas demonstradas no codigo/testes, mas detectar a ausencia de verificacao de papel ou propriedade exige acompanhar middleware e persistencia entre arquivos. Regras locais simplistas tambem acusariam fluxos protegidos. Ver auditoria da rodada 2. |
| `adminSectionChallenge` | A rota Angular possui `AdminGuard`; a existencia da rota nao demonstra bypass da autorizacao. |
| `web3SandboxChallenge`, `scoreBoardChallenge` | Encontrar nomes de rotas de interface ou ausencia de `canActivate` nao demonstra, por si, acesso indevido a dados/operacoes protegidos. |
| `tokenSaleChallenge` | O trecho e um matcher de caminho ofuscado; uma regra que reconhecesse este caminho seria especifica do Juice Shop, nao um detector generico de falha. |
| `redirectCryptoCurrencyChallenge` | As URLs de criptomoedas estao em allowlist explicita. O problema generico de validar URL por substring ja e detectado para `redirectChallenge`; a inclusao de destinos especificos depende da politica do aplicativo. |
| `changeProductChallenge` | A protecao de PUT esta comentada enquanto um recurso REST e gerado dinamicamente. Detectar de forma confiavel ausencia de middleware exige reconstruir essa configuracao, nao apenas casar o comentario. |
| `chatbotPromptInjectionChallenge`, `chatbotGreedyInjectionChallenge` | A politica do cupom esta no prompt; a ferramenta recebe desconto numerico sem limite no schema nem validacao antes de gerar o cupom. O resultado depende de chamadas do modelo e de regras de negocio. Casar o texto `maximum 10` ou o nome do campo criaria uma regra fragil/especifica; nao foi promovida. |

Assim, **nao se conclui** que os dez desafios estejam livres de vulnerabilidade
nem que outro SAST nao os detectaria. Conclui-se apenas que esta rodada nao
produziu regras genericas suficientemente defensaveis para conta-los.

## Reproducao e proxima decisao

```bash
semgrep scan --test rules --metrics=off
python3 scripts/scan_semgrep_exploratorio.py \
  --worktree /tmp/tcc-juiceshop-audit --perfis rodada3 \
  --saida "$(mktemp -d /tmp/tcc-semgrep-rodada3-XXXXXX)"
python3 scripts/build_challenge_matrix.py \
  --worktree /tmp/tcc-juiceshop-audit \
  --scan-extra rodada2=outputs/auditoria_sast/rodada2.json \
  --scan-extra rodada3=outputs/auditoria_sast/rodada3.json \
  --triagem-extra config/auditoria_desafios_rodada2.yaml \
  --triagem-extra config/auditoria_desafios_rodada3.yaml \
  --saida outputs/auditoria_sast/rodada3
python3 scripts/report_rodada3.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

A repeticao deve ser feita com Semgrep `1.177.0`; se nao for a versao do PATH,
use `--semgrep-bin` no script. O conjunto de regras remotas `p/default`
**ainda nao esta congelado**: os JSONs fixam os achados desta auditoria, nao
garantem um re-scan identico apos mudancas no registro. Antes de iniciar uma
nova coorte de correcoes pela LLM, a decisao seguinte e congelar a definicao
das regras e criar testes de regressao de seguranca para os casos selecionados.
O arquivo `outputs/auditoria_sast/candidatos_correcao.csv` permanece a
**selecao anterior de 16 causas/20 desafios**; nao deve ser interpretado como
catalogo atualizado dos 23 desafios desta auditoria.

Atualizacao posterior: a rodada 4, documentada em `docs/auditoria_rodada4.md`,
investiga tambem desafios sem marcadores e amplia a cobertura confirmada.
