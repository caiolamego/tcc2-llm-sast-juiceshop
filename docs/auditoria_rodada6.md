# Rodada 6: parametros duplicados, senha atual, CAPTCHA e revisao SSTI

Esta rodada usa Juice Shop v20.1.1 no commit
`f915bddd82790d0f3018902d36ae9b4241a5f51f`, Semgrep CE `1.177.0` e as
exclusoes anteriores. Nao executa LLM nem modifica o baseline JS001-JS012.

## Resultado e origem dos ganhos

| Perfil exploratorio acumulado | Alertas brutos | Alertas confirmados | Falsos positivos | Inconclusivos | Desafios distintos confirmados |
|---|---:|---:|---:|---:|---:|
| Ate a rodada 5 | 56 | 38 | 16 | 2 | 31 |
| Ate a rodada 6 | **59** | **41** | **16** | **2** | **35** |

As confirmacoes sao por **revisao estatica manual do fluxo**, nao execucao de
exploracoes no servidor. Os tres alertas novos foram confirmados. O quarto
desafio novo veio da revisao de dois alertas ja existentes no mesmo trecho.

| Desafio incluido | Origem | Evidencia principal |
|---|---|---|
| `basketManipulateChallenge` | Novo alerta | `routes/basketItems.ts:42`: valida primeiro BasketId, salva ultimo |
| `changePasswordBenderChallenge` | Novo alerta | `routes/changePassword.ts:39-42`: ausencia da senha atual desativa a verificacao |
| `captchaBypassChallenge` | Novo alerta | `routes/captcha.ts:31`: resposta inclui a solucao do CAPTCHA |
| `sstiChallenge` | Nova associacao, sem novo alerta | `routes/userProfile.ts:61`: eval de expressao extraida do username persistido |

O total de 59 soma `default`, `custom-rules` e rodadas 2 a 6. A matriz tem
90 observacoes porque tambem arquiva baseline e outros perfis sobrepostos.
**Nem 59 nem 90 representam vulnerabilidades independentes.** A matriz
mantem 113 desafios unicos; os 35 confirmados nao constituem recall sobre
113 vulnerabilidades detectaveis por SAST. As regras foram desenvolvidas
apos inspecao do alvo: estes resultados nao sao uma avaliacao cega nem uma
estimativa de precisao em projetos diferentes.

## Analise dos novos alertas

### Manipulacao de cesta

`server.ts:317` preserva o corpo bruto, e `lib/utils.ts:186-197` usa o parser
clarinet para guardar pares inclusive com chaves repetidas. `addBasketItem`
coleta todos os BasketId; em `routes/basketItems.ts:37` verifica o primeiro
contra `user.bid`, mas em :42 usa o ultimo para construir o registro salvo
em :47-49. A autenticacao e a verificacao de estoque anteriores, em
`server.ts:427`, nao corrigem essa divergencia.

O teste oficial `test/cypress/e2e/basket.spec.ts:56-70` documenta o mesmo
fluxo de POST com chaves duplicadas. Foi lido, nao executado. A regra
generica detecta a divergencia entre primeiro valor verificado e ultimo
valor usado. Os testes negativos verificam uso do mesmo valor ou verificacao
do ultimo valor. Pode haver falsos positivos se outro controle garantir
que todos os valores sejam iguais; isso exige revisao manual.

O alerta anterior em `basketItems.ts:68` continua inconclusivo: ele pertence
ao caminho de PUT e aponta uma consulta intermediaria. **A confirmacao do
POST nao transforma aquele alerta em verdadeiro positivo.**

### Troca de senha

A condicao `currentPassword && ...` nao rejeita a ausencia de senha atual.
As verificacoes anteriores validam token, nova senha e repeticao; o caminho
chega a `user.update` em :51. A falha exige sessao/token da vitima, nao
permite trocar anonimamente a senha de qualquer conta. O teste oficial
`test/cypress/e2e/changePassword.spec.ts` documenta uma cadeia com XSS.

A regra diferencia esse padrao de `!current || hash(current) !== stored`
e de uma comparacao obrigatoria. Nao prova ausencia de controles em outros
middlewares, nem distingue sozinha um fluxo legitimo de reset por token.
A confirmacao aqui resulta da leitura do caminho completo.

### CAPTCHA

`captchas()` devolve o mesmo objeto que inclui `captchaId`, `captcha` e
`answer`. `verifyCaptcha` compara a resposta recebida com o valor armazenado.
O teste oficial `test/cypress/e2e/contact.spec.ts:183-222` usa o campo answer
da API para automatizar feedbacks. O fluxo em `server.ts:404-406` nao
acrescenta uso unico; o hook registra quantidade/tempo, nao bloqueia pedidos.

O alerta identifica a exposicao da resposta, nao mede dez pedidos em vinte
segundos. A regra cobre objetos com propriedades captcha/answer enviados por
json; os testes negativos enviam apenas identificador e desafio, mantendo a
solucao no servidor. Nao cobre toda implementacao possivel de CAPTCHA.

## Revisao rastreavel de SSTI

`updateUserProfile.ts:38` persiste username controlado pelo usuario. Em
`userProfile.ts:52-61`, a expressao extraida do campo chega a eval no servidor
quando o caminho esta habilitado. `routes/verify.ts:96-97` e o teste Cypress
`profile.spec.ts` vinculam esse mecanismo a `sstiChallenge`. O teste oficial
contem comandos externos: **nenhum payload dele foi executado**.

`config/revisoes_associacoes_rodada6.yaml` acrescenta SSTI apenas aos dois
alertas exploratorios de `default` nesse trecho. Nao cria alertas, nao remove
a associacao anterior e nao modifica a ocorrencia equivalente do baseline.
Todos os snapshots anteriores permanecem como estavam.

O mecanismo `--revisoes` exige ID do alerta e triagem anterior exata, aceita
somente desafios adicionais validos em alertas ja confirmados, exige motivo
e recusa modificar baseline. A matriz salva o antes/depois e hash do arquivo
de revisoes. O comparador reproduz somente essas mudancas autorizadas; outras
alteracoes em linhas, regras, triagem ou scans anteriores falham na validacao.

## Scans, timeout e verificacao

O primeiro scan, `outputs/auditoria_sast/rodada6.json`, foi preservado com
3 alertas e 1 aviso de timeout da regra first-last-mismatch em
`frontend/src/assets/private/three.js`. Ele nao foi somado ao acumulado.

Repetimos com **30 segundos por regra/arquivo**, sem trocar versao ou
exclusoes. O resultado usado na matriz esta em
`outputs/auditoria_sast/rodada6/scan_completo/rodada6.json`: 3 alertas e
zero avisos. O manifesto ao lado registra o timeout e hashes. Esse limite
maior e uma diferenca operacional explicita em relacao ao primeiro scan.

Os testes incluem exemplos positivos/negativos das regras, preservacao do
baseline, rejeicao de revisoes nao declaradas, triagem anterior divergente,
chaves invalidas e linhas duplicadas na matriz. Testes de integracao do Juice
Shop nao foram executados; a validacao aqui nao substitui testes de seguranca
e regressao para futuras correcoes.

## Reproduzir

Semgrep 1.177.0 deve estar no PATH; alternativamente passe `--semgrep-bin`.
O scan abaixo usa diretorio temporario para preservar os arquivos arquivados.

```bash
semgrep scan --test rules --metrics=off
python3 scripts/scan_semgrep_exploratorio.py \
  --worktree /tmp/tcc-juiceshop-audit --perfis rodada6 --timeout 30 \
  --saida "$(mktemp -d /tmp/tcc-semgrep-rodada6-XXXXXX)"
python3 scripts/build_challenge_matrix.py \
  --worktree /tmp/tcc-juiceshop-audit \
  --scan-extra rodada2=outputs/auditoria_sast/rodada2.json \
  --scan-extra rodada3=outputs/auditoria_sast/rodada3.json \
  --scan-extra rodada4=outputs/auditoria_sast/rodada4.json \
  --scan-extra rodada5=outputs/auditoria_sast/rodada5.json \
  --scan-extra rodada6=outputs/auditoria_sast/rodada6/scan_completo/rodada6.json \
  --triagem-extra config/auditoria_desafios_rodada2.yaml \
  --triagem-extra config/auditoria_desafios_rodada3.yaml \
  --triagem-extra config/auditoria_desafios_rodada4.yaml \
  --triagem-extra config/auditoria_desafios_rodada5.yaml \
  --triagem-extra config/auditoria_desafios_rodada6.yaml \
  --revisoes config/revisoes_associacoes_rodada6.yaml \
  --saida outputs/auditoria_sast/rodada6
python3 scripts/report_rodada6.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

## Proximas oportunidades, ainda fora da cobertura confirmada

| Prioridade | Candidato e evidencia inspecionada | O que falta para contar |
|---|---|---|
| Alta | `forgedReviewChallenge`: `updateProductReviews.ts` seleciona `_id` recebido sem autor; usuario autenticado e usado no hook posterior | Revisar os middlewares e testar regra de escrita sem escopo de autor, com negativo que filtra pelo usuario. Nao confundir com o alerta ja existente de operador NoSQL/multi-update. |
| Alta | `freeDeluxeChallenge`: `deluxe.ts` verifica wallet e card em dois ifs, mas atualiza role depois deles | Demonstrar caminho de modo desconhecido e testar um padrao que diferencie rejeicao obrigatoria de fall-through. |
| Media | `dataExportChallenge`: `dataExport.ts` troca vogais do email por asteriscos antes de selecionar pedidos | Demonstrar colisao entre identidades e viabilidade no fluxo de cadastro/exportacao. Uma consulta por email normalizado, sozinha, nao comprova vazamento. |
| Media | `negativeOrderChallenge`: `basketItems.ts` verifica limites superiores de quantidade, e `order.ts` multiplica preco pela quantidade | Conferir todo o caminho de validacao/modelo e testar entrada negativa contra exemplo com limite inferior. |

Nao ha promessa de um novo desafio para cada regra. Os candidatos acima sao
hipoteses fundamentadas para a proxima rodada, nao resultados desta rodada.
Upload, YAML e desafios dependentes de deployment continuam com as limitacoes
anteriores; nao foram classificados como ausencia de vulnerabilidade.

Antes da LLM, ainda sera preciso ampliar e congelar a selecao de causas
independentes. `outputs/auditoria_sast/candidatos_correcao.csv` continua sendo
o catalogo antigo de 16 causas/20 desafios, nao a selecao dos 35 atuais.
Falsos positivos e inconclusivos permanecem registrados, fora das tentativas
de correcao ate nova revisao. A execucao da LLM continua a cargo do usuario.
