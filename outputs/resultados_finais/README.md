# Resultados finais com classificação OWASP complementar

A versão atual é [`OWASP_20261111_V1/`](OWASP_20261111_V1/), publicada por
consolidação offline em 11/11/2026 a partir das campanhas reais de 06/11/2026.
São 78 casos por modelo e a mesma definição principal de F (`criterio`).
Não houve nova execução de modelos, SAST, testes ou aplicação de patches.

| Modelo | Pasta na versão atual | Casos aceitos |
|---|---|---:|
| GPT-4.1 mini | `AMP_REAL_20261106T151004Z_f49ac0d2/` | 38/78 |
| GPT-5.6 Luna | `AMP_REAL_20261106T125801Z_0eb68fe4/` | 51/78 |
| GPT-6 Luna | `AMP_REAL_20261106T105533Z_aa697342/` | 49/78 |

## O que consultar

Em cada pasta de campanha desta consolidação:

- `metricas.json`: métricas completas, incluindo proveniência da classificação.
- `metricas_por_owasp.csv`: métricas por categoria com o complemento aplicado.
- `metricas_por_owasp_original.csv`: agrupamento original, incluindo os sem categoria.
- `tentativas.csv`: categoria usada em `owasp_2025`, com categoria original e método
  nas colunas `owasp_2025_original` e `owasp_classificacao_metodo`.
- `casos.csv`: os mesmos campos de classificação junto ao aceite por caso.
- `metricas_gerais.csv` e demais agrupamentos: preservam os resultados anteriores.
- `manifesto.json`: hashes de fontes e arquivos publicados.

A raiz da versão contém `aceites_por_owasp.csv`, resumo dos aceites por caso,
e `conferencia.json`, que registra as comparações com a consolidação anterior.
Os CSVs de métricas por OWASP são por tentativa/população/definição de F;
o resumo de aceites por caso usa um denominador diferente. Não confundir as taxas.

## Procedimento e limites

A configuração versionada está em
[`config/classificacao_owasp/v1/`](../../config/classificacao_owasp/v1/README.md).
Mantém 29 categorias e completa 49 casos: 41 por correspondência explícita de
CWE e oito por interpretação contextual documentada. O agrupamento inclui
falsos positivos e inconclusivos, sem convertê-los em vulnerabilidades confirmadas.
As oito decisões não foram submetidas a revisão humana independente.

Os registros brutos e artefatos continuam em `outputs/campanha_docker/<EXECUCAO>/`;
as métricas publicadas anteriormente continuam em `outputs/rris/<EXECUCAO>_METRICAS/`.
Os identificadores com `SEMOWASP` descrevem a condição original da campanha e
não são renomeados retroativamente. A classificação nova está nos consolidados.

## Reprodução

A partir da raiz do repositório, forneça um destino novo:

```sh
python3 scripts/relatorios/atualizar_resultados_finais.py \
  --saida outputs/resultados_finais/NOVA_VERSAO
```

O comando usa apenas as fontes deste repositório, sem depender do repositório
de escrita. Confere igualdade das métricas gerais, aceites, custos, tempos, RRIS
e agrupamentos não OWASP; o agrupamento OWASP original deve coincidir byte a
byte com o CSV anterior. Os manifestos individuais verificam as entradas antes
da publicação. O destino existente é recusado, preservando versões publicadas.
