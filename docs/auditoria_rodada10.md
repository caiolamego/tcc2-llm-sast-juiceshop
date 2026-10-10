# Rodada 10 — cupons e validade temporal

Os dois candidatos foram confirmados por revisão do fluxo e testes isolados
do código real: `forgedCouponChallenge` e `manipulateClockChallenge`.
Nenhuma LLM foi executada e o alvo não foi alterado.

| Perfil exploratório acumulado | Rodada 9 | Rodada 10 |
|---|---:|---:|
| Alertas brutos | 72 | 74 |
| Confirmados pela revisão | 49 | 51 |
| Falsos positivos | 21 | 21 |
| Inconclusivos | 2 | 2 |
| Desafios distintos confirmados | 43 | 45 |

Perfis somados: `default`, `custom-rules`, rodadas 2–10. A matriz preserva
também scans históricos sobrepostos, totalizando 105 observações; esse total
não representa vulnerabilidades distintas. Permanecem 113 chaves únicas.

## Confirmação e limites

### Cupom sem autenticidade

`lib/insecurity.ts:112` converte em inteiro o percentual obtido de Z85.
Formato e mês são validados, mas não há assinatura nem consulta a uma emissão
confiável. A entrada vem de `routes/coupon.ts`, é gravada na cesta e consumida
por `calculateApplicableDiscount` em `routes/order.ts`. Os endpoints de cesta
passam por autenticação; isso não impede o próprio cliente de escolher o cupom.

O teste usa z85 0.0.2, `discountFromCoupon`, `applyCoupon` e o trecho de cálculo
do preço reais. Um valor codificado pelo teste, sem emissão pelo servidor,
produz desconto de 90%, persiste na cesta simulada e reduz subtotal 100 para 10.
Um controle HMAC apenas no harness rejeita o valor alterado com a assinatura
anterior, mas aceita o original. Cupons de mês vencido e ausência de cupom
também são testados. A regra é um sinal de integridade de baixa confiança:
decodificar um número não prova falha sem analisar origem e uso sensível.

### Data de campanha controlada pelo cliente

`routes/order.ts:201` compara a data retirada de `req.body.couponData`, após
Base64, com `campaign.validOn`. O relógio do servidor aparece no hook do
desafio, não como condição para autorizar o desconto.

Com relógio de teste fixado em 10/10/2026, a função real aceita a data esperada
da campanha de 2019 e o cálculo real reduz subtotal 100 para 25. Uma data
incorreta não aplica desconto. O controle ilustrativo por dia UTC do servidor
rejeita a campanha vencida e aceita o dia vigente; isso não é um patch nem
uma decisão definitiva sobre fuso e política comercial.

Os testes são **isolados, não HTTP/E2E**: não exercitam checkout completo,
pagamento real, banco, login ou navegador. Cesta, saída de PDF e hooks são
simulados; o cálculo é extraído do código real. Z85 é a dependência real,
com lockfile arquivado; Node utilizado: 24.14.0. O relógio fixo é injetado nas
funções, sem alterar o relógio do sistema.

As regras não utilizam nomes de desafios, caminhos exclusivos ou linhas.
Fixtures positivos e seguros passaram; controles externos de assinatura ou
validade ainda podem gerar falsos positivos, explicitamente documentados nos
fixtures. Nenhum novo falso positivo foi encontrado nos dois alertas deste
scan. Isso não demonstra precisão geral de 100% fora deste alvo.

## Verificação e preservação

- Dois scans com achados equivalentes, zero avisos/timeouts, Semgrep 1.177.0,
  timeout de 30 segundos e exclusões existentes. Manifestos incluem hashes.
- Quatro testes de mecanismo aprovados e evidências TAP arquivadas.
- Comparação exige preservação dos alertas, triagens, scans anteriores e
  revisão SSTI, além das 113 chaves únicas e referências válidas.
- Baseline JS001–JS012, catálogo antigo de correção e alvo limpo preservados.

## Encerramento da expansão

O relatório mantém os dez candidatos prioritários fixos e registra oito
confirmados após as rodadas 8–10. A meta de pelo menos sete foi atingida
(80%). A expansão encerra aqui: `timingAttackChallenge` e `emailLeakChallenge`
não foram investigados nesta sequência e não serão iniciados automaticamente.

Isso conclui a **rodada 10 e a meta de cobertura**, não toda a preparação do
experimento. Ainda falta consolidar uma seleção versionada de causas para
correção, revisar duplicatas/causas diferentes no mesmo trecho e definir os
testes de regressão de cada caso antes da LLM. A estimativa anterior de causas
não é resultado definitivo; o catálogo antigo continua sem representar toda
a cobertura atual. Não foram gerados prompts nem tentativas de correção.

## Artefatos e reprodução

- [Matriz CSV](../outputs/auditoria_sast/rodada10/matriz_desafios.csv) e JSON no mesmo diretório.
- [Resumo e contador dos prioritários](../outputs/auditoria_sast/rodada10/resumo.json).
- [Scan](../outputs/auditoria_sast/rodada10.json), [manifesto](../outputs/auditoria_sast/manifesto-rodada10.json)
  e repetição em `outputs/auditoria_sast/rodada10/repeticao`.
- [Triagem](../config/auditoria_desafios_rodada10.yaml),
  [testes](../outputs/auditoria_sast/rodada10/testes/testes.tap) e manifesto/lockfile no mesmo diretório.

Usar o checkout limpo no commit `f915bddd82790d0f3018902d36ae9b4241a5f51f`.
Da raiz do repositório, com Semgrep 1.177.0:

```bash
semgrep --test --config rules rules
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/scan_semgrep_exploratorio.py --worktree /caminho/juice-shop --perfis rodada10 --timeout 30 --saida /caminho/novo-scan
npm ci --prefix outputs/auditoria_sast/rodada10/testes/dependencias --no-audit --no-fund
JUICE_SHOP_WORKTREE=/caminho/juice-shop ROUND10_DEPS="$PWD/outputs/auditoria_sast/rodada10/testes/dependencias" node --test scripts/test_rodada10_flows.mjs
```

`scripts/verify_rodada10.py` recebe `--worktree`, `--deps` e `--saida` nova
para arquivar outra execução sem sobrescrever os resultados anteriores.
Para regenerar a matriz em diretório novo (Bash):

```bash
audit_args=()
for round in 2 3 4 5 6 7 8 9 10; do
  scan_path="outputs/auditoria_sast/rodada${round}.json"
  if [ "$round" = 6 ] || [ "$round" = 9 ]; then
    scan_path="outputs/auditoria_sast/rodada${round}/scan_completo/rodada${round}.json"
  fi
  audit_args+=(--scan-extra "rodada${round}=${scan_path}" --triagem-extra "config/auditoria_desafios_rodada${round}.yaml")
done
python3 scripts/build_challenge_matrix.py --worktree /caminho/juice-shop "${audit_args[@]}" --revisoes config/revisoes_associacoes_rodada6.yaml --saida /caminho/nova-matriz
python3 scripts/report_rodada10.py
```
