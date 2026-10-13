# Rodada 11 — concorrência e JSONP

Expansão adicional solicitada explicitamente após a meta da rodada 10.
Não altera o encerramento histórico anterior, não executa LLM e não inicia
novas rodadas. O código-alvo e o baseline JS001–JS012 permanecem intactos.

| Perfil ampliado acumulado | Antes | Depois |
|---|---:|---:|
| Alertas brutos | 74 | 76 |
| Confirmados por revisão | 51 | 53 |
| Falsos positivos | 21 | 21 |
| Inconclusivos | 2 | 2 |
| Desafios distintos confirmados | 45 | 47 |

Os dez candidatos prioritários passam a incluídos, **com confirmação
condicional de JSONP** descrita abaixo. Não são dez falhas independentes
automaticamente nem cobertura universal de deployments. O perfil somado é
`default`, `custom-rules` e rodadas 2–11. A matriz mantém 113 chaves únicas
e os scans históricos sobrepostos (107 observações, não 107 vulnerabilidades).

## Concorrência nas curtidas

`routes/likeProductReviews.ts` verifica a ausência do email em `likedBy`,
incrementa `likesCount`, espera 150ms e só depois registra a identidade.
Autenticação no servidor e na rota não torna essas operações atômicas.
A regra aponta o incremento antes da espera; a confirmação exige examinar
o fluxo inteiro, não apenas detectar uma chamada a sleep.

Teste da rota original com MarsDB 0.6.11 real e identidade simulada:

- Duas chamadas sequenciais resultam em sucesso e depois 403.
- Três chamadas intercaladas antes do registro de identidade resultam em
  três sucessos, contador 3 e três entradas do mesmo email; cenário repetido
  três vezes.
- Controle com filtro de elegibilidade e `$inc`/`$addToSet` na mesma operação
  conserva contador 1 e uma entrada. É controle do harness, não patch do alvo
  nem prova de atomicidade em todo banco/deployment possível.

A primeira tentativa com disparo simultâneo perdeu incrementos no MarsDB:
observou contador 1, não 3. O teste final controla o escalonamento iniciando
cada chamada após observar o incremento anterior, ainda dentro da janela
real de 150ms. Não substitui o sleep da rota nem simula as operações do banco.
Essa distinção evita ocultar a corrida sob outro comportamento concorrente.
Não há teste HTTP de carga nem avaliação estatística de probabilidade.

## JSONP: condição de exploração demonstrada

`routes/currentUser.ts:58` responde com dados de sessão em JSONP quando há
callback. A regra genérica também apontaria JSONP público legítimo: a presença
de callback não é prova de vazamento. A revisão observa verificação do token,
cache de usuário, conteúdo do email e configuração do cookie.

Teste de navegador com Express 4.22.1, rota original e Chromium 121.0.6167.57:

1. `victim.example.test` recebe cookie host-only, com os defaults de
   `res.cookie('token', token)` de `lib/insecurity.ts`. O navegador informa Lax.
2. Uma página em `attacker.example.test`, origem distinta mas mesmo site,
   carrega a resposta como script e recebe o email pelo callback.
3. O host atacante **não recebe o cookie** em suas próprias requisições.
   Assim, não se confunde exposição JSONP com compartilhamento do cookie
   pelo mesmo host em outra porta.
4. De `other.invalid.test` (outro site), o callback não obtém email: Lax
   impede que o cookie acompanhe esse carregamento cross-site.
5. O controle que responde JSON em vez de JSONP não executa o callback.

**Conclusão limitada:** vazamento demonstrado para um atacante que controla
uma origem irmã no mesmo site, com vítima autenticada. Não foi demonstrado
vazamento a qualquer site arbitrário com cookies Lax. Não se afirma que o
deployment real possua um subdomínio controlável por atacante.

Todos os hosts `.test` são mapeados pelo Chromium para 127.0.0.1; listeners
apenas em loopback. Dados são sintéticos. A verificação JWT e o cache de
identidade são simulados; login completo, frontend e implantação não são
exercitados. Não há bypass de assinatura sendo testado. Chromium é uma versão
fixada antiga, não validação de todos os navegadores atuais. Antes de uma
alegação sobre deployment real, repetir com seu domínio, TLS, cookie, login
e navegador efetivos. A condição acompanha a triagem e o resumo.

## Regras, evidências e preservação

Regras genéricas sem nomes de desafios/caminhos do alvo/linhas. Fixtures
documentam exemplos seguros e falsos positivos conhecidos: lock externo para
concorrência e conteúdo intencionalmente público para JSONP. A triagem dos
dois alertas do alvo foi realizada por mecanismo, não por proximidade.

- Dois scans equivalentes com zero avisos/timeouts; Semgrep 1.177.0,
  timeout de 30 segundos, commit e exclusões existentes.
- Três testes de fluxo, incluindo navegador e controle atômico, aprovados.
- Manifestos com hashes de regras, scans, fontes, testes e lockfile.
- Comparação rejeita alteração de alertas/triagens anteriores e da revisão SSTI.
- Nenhuma alteração no catálogo antigo para correção. Agrupamento de causas
  independentes e seleção versionada ainda são trabalhos de consolidação.

## Artefatos e reprodução

[Matriz CSV](../../outputs/auditoria_sast/rodada11/matriz_desafios.csv), JSON no
mesmo diretório, [resumo](../../outputs/auditoria_sast/rodada11/resumo.json),
[triagem](../../config/auditoria_desafios_rodada11.yaml),
[scan](../../outputs/auditoria_sast/rodada11.json) e
[testes TAP](../../outputs/auditoria_sast/rodada11/testes/testes.tap).
Repetição e manifestos em `outputs/auditoria_sast/rodada11/repeticao` e `testes`.

Alvo limpo no commit `f915bddd82790d0f3018902d36ae9b4241a5f51f`; Node 24.14.0.
Dependências fixadas: marsdb 0.6.11, express 4.22.1, cookie-parser 1.4.7,
playwright 1.41.2. Instalar somente no diretório isolado, não no alvo:

```bash
npm ci --prefix outputs/auditoria_sast/rodada11/testes/dependencias --no-audit --no-fund
outputs/auditoria_sast/rodada11/testes/dependencias/node_modules/.bin/playwright install chromium
JUICE_SHOP_WORKTREE=/caminho/juice-shop ROUND11_DEPS="$PWD/outputs/auditoria_sast/rodada11/testes/dependencias" node --test tests/integration/rodada11/test.mjs
semgrep --test --config rules rules
python3 -m unittest discover -s tests/unit -p 'test_*.py'
python3 scripts/audit/scan_semgrep_exploratorio.py --worktree /caminho/juice-shop --perfis rodada11 --timeout 30 --saida /caminho/novo-scan
```

`verify_rodada11.py` recebe `--worktree`, `--deps`, `--saida` inexistente e
arquiva evidência sem sobrescrever. Para regenerar a matriz, usar o comando
da rodada 10 acrescentando `11` ao loop de perfis/triagens e escolher saída
nova. O scan inicial completo desta rodada é `outputs/auditoria_sast/rodada11.json`.
`python3 scripts/reports/report_rodada11.py` compara os snapshots arquivados 10 e 11.
