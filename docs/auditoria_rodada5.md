# Rodada 5: consulta por ID e avaliacao de expressoes B2B

Alvo: Juice Shop v20.1.1, commit `f915bddd82790d0f3018902d36ae9b4241a5f51f`.
Semgrep CE `1.177.0`, mesmas exclusoes de `config/semgrepignore`.
Baseline JS001-JS012, scans e matrizes anteriores permanecem intactos.
Nenhuma LLM foi executada.

## Resultado

| Perfil acumulado | Alertas brutos | Confirmados por revisao estatica | Falsos positivos | Inconclusivos | Desafios distintos confirmados |
|---|---:|---:|---:|---:|---:|
| Ate a rodada 4 | 51 | 35 | 15 | 1 | 28 |
| Ate a rodada 5 | **56** | **38** | **16** | **2** | **31** |

O perfil acumulado soma default, custom-rules e rodadas 2 a 5. A matriz
arquiva tambem os perfis sobrepostos baseline, security-audit e
angular-sanitizer-bypass: seus **87 registros nao sao 87 falhas distintas**.
A matriz continua com 113 chaves de desafio unicas e referencias verificadas
contra arquivos e linhas do commit fixado.

| Novo alerta | Triagem | Correspondencia a desafios |
|---|---|---|
| `routes/b2bOrder.ts:23` | Confirmado: entrada do corpo interpretada por notevil dentro de VM | `rceChallenge`, `rceOccupyChallenge` |
| `routes/basket.ts:19` | Confirmado: busca e resposta de cesta sem conferir proprietario | `basketAccessChallenge` |
| `routes/basketItems.ts:68` | Inconclusivo: consulta intermediaria antes da API gerada | Nenhum confirmado |
| `routes/delivery.ts:34` | Falso positivo: catalogo publico de formas de entrega | Nenhum |
| `routes/order.ts:35` | Confirmado: checkout usa cesta da URL sem conferir proprietario | Nenhum desafio atribuido |

Portanto, sao **5 novos alertas, 3 alertas confirmados e 3 novos desafios**.
Esses numeros coincidem apenas por acaso: B2B tem um alerta para dois desafios;
checkout tem uma falha confirmada sem correspondencia exata ao catalogo.
Os dois desafios B2B compartilham um ponto de correcao, nao dois casos
independentes para medir o desempenho da LLM.

## Evidencia e limites

As duas regras em `rules/rodada5/` nao contem chaves de desafio, nomes de
modelos do Juice Shop ou numeros de linha.

- **Consulta por ID:** segue `req.params` ate `findOne` cujo `where` contem
  somente `id`. Os exemplos protegidos usam escopo de proprietario ou ID vindo
  da identidade autenticada. A regra e de auditoria: nao entende permissoes
  externas nem verificacoes posteriores. Um exemplo protegido por verificacao
  posterior e intencionalmente marcado como alerta esperado, documentando esse
  falso positivo conhecido. Isso nao e uma prova automatica de IDOR.
- **B2B:** correlaciona importacao do avaliador notevil, dado de campo de objeto
  com valor padrao, contexto VM e chamada ao mesmo avaliador dentro da string
  executada. A origem HTTP foi conferida manualmente. O teste usa nomes de
  variaveis diferentes dos do alvo. JSON.parse e expressao constante sao
  exemplos negativos. A regra nao cobre todos os avaliadores nem todos os
  formatos de propagacao de dados.

Em `routes/basket.ts:18-31`, o objeto selecionado pelo parametro de rota e
devolvido sem validar dono. `server.ts:356` autentica; `appendUserId`, em
`lib/insecurity.ts:175-185`, apenas escreve `req.body.UserId`, que essa consulta
ignora. A comparacao com `user.bid` registra a solucao, nao impede a resposta.
O teste oficial `test/api/basket.test.ts:111` documenta leitura de outra cesta.

Em `routes/b2bOrder.ts:17-32`, o corpo da requisicao entra no avaliador e ha
tratamento separado para limite de iteracoes e timeout. Os testes oficiais
em `test/api/b2b-order.test.ts` documentam esses dois caminhos. **Foram lidos,
nao executados nesta rodada.** A confirmacao e estatica do mecanismo e da
associacao, nao prova de indisponibilidade medida, escape da VM ou execucao
de comandos do sistema. O timeout de 2 segundos existe, e o caminho depende
de os desafios estarem habilitados (o catalogo os desabilita em Docker/Heroku).

No checkout, `routes/order.ts:34-54` seleciona uma cesta da URL, usa seus
produtos para o pedido e remove seus itens ao finalizar, sem comparar dono.
`server.ts:356,604` nao acrescenta essa validacao. A falha foi registrada sem
forcar uma associacao com desafios de leitura ou adicao de produtos.

## Investigacoes ainda sem novo alerta confirmado

- **Manipulacao de itens:** a consulta alertada em `basketItems.ts` nao e a
  escrita feita pelo finale-rest. Falta validar o caminho completo de mutacao;
  nao foi confirmado `basketManipulateChallenge` pela proximidade do hook.
- **Upload de tamanho:** `server.ts:692` ja limita a 200000 bytes; o desafio
  usa 100000 em `fileUpload.ts:57`. Uma regra de ausencia de limite seria
  incorreta; a discrepancia exige conhecer a politica funcional da aplicacao.
- **Upload de tipo:** `checkFileType` registra o desafio e chama `next`, mas
  os handlers seguintes tratam extensoes de formas diferentes. Nao foi criada
  uma regra baseada no nome do hook ou no nome do desafio.
- **YAML:** `fileUpload.ts:109` carrega YAML e serializa com JSON.stringify
  dentro de VM com timeout. Apenas detectar `yaml.load` nao demonstra bomba
  YAML. Faltam teste limitado de expansao/recursos e exemplos protegidos que
  uma regra consiga diferenciar; nao entrou na cobertura confirmada.
- **SSTI:** permanece candidata a nova associacao de alerta ja existente em
  `userProfile.ts:61`. Esta rodada nao alterou retroativamente a triagem antiga.
  Uma revisao futura precisa versionar essa reclassificacao explicitamente;
  nao representaria um alerta bruto novo.

Esses casos nao sao ausencia de vulnerabilidade. Permanecem pendencias de
demonstracao e/ou de vinculacao confiavel por SAST.

## Reproduzir

Use Semgrep 1.177.0 no PATH ou passe `--semgrep-bin` ao script de scan.
O diretorio temporario evita sobrescrever os resultados arquivados.

```bash
semgrep scan --test rules --metrics=off
python3 scripts/scan_semgrep_exploratorio.py \
  --worktree /tmp/tcc-juiceshop-audit --perfis rodada5 \
  --saida "$(mktemp -d /tmp/tcc-semgrep-rodada5-XXXXXX)"
python3 scripts/build_challenge_matrix.py \
  --worktree /tmp/tcc-juiceshop-audit \
  --scan-extra rodada2=outputs/auditoria_sast/rodada2.json \
  --scan-extra rodada3=outputs/auditoria_sast/rodada3.json \
  --scan-extra rodada4=outputs/auditoria_sast/rodada4.json \
  --scan-extra rodada5=outputs/auditoria_sast/rodada5.json \
  --triagem-extra config/auditoria_desafios_rodada2.yaml \
  --triagem-extra config/auditoria_desafios_rodada3.yaml \
  --triagem-extra config/auditoria_desafios_rodada4.yaml \
  --triagem-extra config/auditoria_desafios_rodada5.yaml \
  --saida outputs/auditoria_sast/rodada5
python3 scripts/report_rodada5.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

O manifesto novo registra hashes das regras e do JSON. O comparador exige
que scans, alertas e triagens anteriores estejam identicos, sem perda de
desafios confirmados. O scan nao inclui testes oficiais nem codefixes.

O catalogo `outputs/auditoria_sast/candidatos_correcao.csv` continua sendo a
selecao anterior de 16 causas/20 desafios. **Nao e a selecao atualizada de 31
desafios.** Falsos positivos e inconclusivos desta rodada ficam registrados,
fora de uma futura selecao de correcoes ate revisao. O proximo passo concreto
e validar a mutacao de itens e versionar a associacao SSTI; a selecao ampliada
para a LLM deve ser congelada separadamente, agrupando causas compartilhadas.
