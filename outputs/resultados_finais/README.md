# Resultados finais com classificação OWASP complementar

A versão atual é [`OWASP_20261111_V2/`](OWASP_20261111_V2/), publicada por
consolidação offline em 11/11/2026 a partir das campanhas reais de 06/11/2026.
São 78 casos por modelo e a mesma definição principal de F (`criterio`).
Não houve nova execução de modelos, SAST, testes ou aplicação de patches.

| Modelo | Pasta na versão atual | Casos aceitos |
|---|---|---:|
| GPT-4.1 mini | `AMP_REAL_20261106T151004Z_f49ac0d2/` | 38/78 |
| GPT-5.6 Luna | `AMP_REAL_20261106T125801Z_0eb68fe4/` | 51/78 |
| GPT-6 Luna | `AMP_REAL_20261106T105533Z_aa697342/` | 49/78 |

## Artefatos com a categoria no nome

Cada pasta de execução da versão V2 contém:

- `campanha/`: prompts, respostas, patches, códigos corrigidos, scans, testes,
  comparação de alertas e registros, com a categoria OWASP revisada nos nomes.
- `rris/`: cópia da evidência conjunta, com os mesmos nomes revisados nos patches
  e referências atualizadas no manifesto.
- `metricas/`: consolidados calculados a partir dessas cópias verificadas.

O campo de categoria do identificador mudou de `SEMOWASP` para `A01` a `A08`,
conforme a classificação revisada de cada caso. Os outros campos foram mantidos.
Exemplo: `AMP20721d202c8b96d6_SEMOWASP_OUTRO_P1_AMP_REAL_20261106T105533Z_aa697342`
passou a `AMP20721d202c8b96d6_A05_OUTRO_P1_AMP_REAL_20261106T105533Z_aa697342`.

`mapa_artefatos.csv` relaciona os caminhos antigos e atuais e seus hashes.
`mapa_tentativas.csv` relaciona os identificadores. O registro JSONL e o CSV de
tentativas preservam o identificador antigo em `tentativa_id_original`.
Todos os arquivos das fontes são preservados. Somente os índices de tentativas,
sessões e manifesto RRIS foram reescritos nas cópias; os conteúdos experimentais
foram conferidos byte a byte. Os hashes desses índices derivados constam do mapa.

## O que consultar

Na subpasta `metricas/` de cada execução:

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
Os identificadores com `SEMOWASP` nas fontes históricas descrevem a condição
original. Os artefatos usados pela versão V2 e suas referências já usam a categoria
revisada. A versão V1, que tinha apenas os consolidados atualizados, foi preservada.

## Reprodução

A partir da raiz do repositório, forneça um destino novo:

```sh
python3 scripts/relatorios/padronizar_artefatos_finais.py \
  --saida outputs/resultados_finais/NOVA_VERSAO
```

O comando usa apenas as fontes deste repositório, sem depender do repositório
de escrita. Confere os hashes dos conteúdos copiados, a ausência de colisões de
nomes, as referências dos registros, as métricas gerais, aceites, custos, tempos
e RRIS. Na comparação da RRIS, os IDs revisados são relacionados aos originais
pelo mapa, pois a seleção é a mesma. Os manifestos individuais verificam as
entradas antes da publicação. O destino existente é recusado, preservando versões.

Para reproduzir apenas o recorte V1, sem copiar os artefatos nem ajustar seus
nomes, permanece disponível `scripts/relatorios/atualizar_resultados_finais.py`.
