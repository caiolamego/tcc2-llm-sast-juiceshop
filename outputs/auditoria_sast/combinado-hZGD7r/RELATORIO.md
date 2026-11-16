# Revisão do scan combinado de 124 findings

Scan realmente executado com p/default e rules, Semgrep 1.177.0, commit fixado
limpo. Reproduziu 124 findings, 335 regras executadas e 1002 arquivos analisados.
Não aplicou as exclusões adicionais do experimento: classificação de escopo
foi feita depois, preservando todos os findings no JSON e na tabela.

| Métrica | Rodada 12 arquivada | Novo scan combinado |
|---|---:|---:|
| Alertas brutos | 78 | 124 |
| Fora do escopo histórico | 0 | 46 |
| Alertas no escopo histórico | 78 | 78 |
| Alertas confirmados por evidência/revisão | 55 | 55 |
| Falsos positivos no escopo | 21 | 21 |
| Inconclusivos no escopo | 2 | 2 |
| Desafios confirmados | 50 | 50 |

Os 46 adicionais são 31 em `data/static/codefixes/`, 13 em `.github/`, um em
`.npmrc` e um em `frontend/.npmrc`. Fora de escopo não significa falso positivo
ou ausência de problema: eles não são contados como falhas da aplicação no
experimento. Nenhuma solução foi executada ou usada em prompt; findings nesses
arquivos foram excluídos da associação a desafios.

## Método de confirmação

O classificador verifica commit limpo, versão e hashes das regras locais.
Transfere revisão somente quando coincidem regra normalizada, arquivo e
intervalo completo. Prefixos de diretórios nos IDs locais são normalizados
sem alterar o JSON bruto. Não há associação por proximidade de linhas.

Há uma revisão explícita em `revisao.json`: a associação do eval de
`routes/userProfile.ts:61` a SSTI, revisada na rodada 6, divergia do baseline
mais antigo. A revisão final conserva o resultado da matriz 12 e o fluxo
username persistido → expressão → eval. Nenhuma associação histórica foi
reescrita. A triagem preliminar `triagem-v1` permanece arquivada.

Os 50 desafios anteriores reapareceram. Nenhum desafio novo foi confirmado.
Os outros 63 estão classificados como `nao_confirmado_neste_scan`, não como
seguros ou inexistentes. Mantêm-se todas as precondições das evidências
históricas, especialmente JSONP entre origens do mesmo site. Esta execução
não repetiu os testes de exploração ou regressão das rodadas anteriores.

## Limitações

O JSON contém **50 avisos de parsing**: 20 erros de sintaxe e 30 casos de
parsing parcial. Não houve timeout reportado. A mensagem de sucesso do CLI
não significa análise completa dos arquivos afetados. A lista integral dos
avisos está no scan e no resumo final. O pacote remoto p/default não está
congelado; repetir no futuro pode produzir resultado diferente.

## Entregas

- [124 alertas classificados](triagem-final/alertas_classificados.csv): status,
  justificativa, referências históricas, regra, arquivo e intervalo.
- [113 desafios classificados](triagem-final/matriz_desafios.csv): filtrar
  `confirmacao=confirmado` para ver os 50 e seus números de alerta.
- [Resumo final](triagem-final/resumo.json), JSONs detalhados no mesmo diretório.
- [Scan bruto](scan.json), [manifesto](manifesto.json), [revisão explícita](revisao.json).

Reprodução da classificação, da raiz do projeto, usando diretório novo:

```bash
python3 scripts/classify_combined_scan.py \
  --scan outputs/auditoria_sast/combinado-hZGD7r/scan.json \
  --worktree /tmp/tcc-juiceshop-audit \
  --revisao outputs/auditoria_sast/combinado-hZGD7r/revisao.json \
  --saida /caminho/nova-classificacao
```

Baseline, snapshots anteriores, alvo e catálogo de correção não foram
alterados. Nenhuma LLM foi executada.
