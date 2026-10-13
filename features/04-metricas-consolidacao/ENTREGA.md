# Entrega da feature 04 — Métricas e consolidação

**Data:** 13/10/2026.  
**Status:** implementada e validada offline.  
**Publicação:** alterações locais, sem commit, push, chamadas à LLM, novos scans ou patches.

## Resultado verificado

- Camada reutilizável de leitura, normalização, cálculo, RRIS e exportação implementada.
- Interface/imports históricos preservados; E01/E02 reproduzidos em cópias temporárias.
- **153 testes passaram:** 115 iniciais + 38 novos; nenhuma falha preexistente no teste inicial.
- Dois relatórios finais com **13 artefatos cada**, reproduzidos byte a byte em novas saídas temporárias.
- **898 arquivos históricos** em outputs/config/rules/knowledge_base conservaram os hashes capturados antes da implementação.
- Zero custo conhecido de API nas validações: nenhuma chamada à LLM foi realizada.

## Relatórios oficiais desta entrega

| Entrada | Referência final | Resultado |
|---|---|---|
| AMP_DRY_01 | [JSON final](../../outputs/feature04/AMP_DRY_01_METRICAS_V2/metricas.json) | 2 tentativas simuladas; nenhuma real |
| AMP_RAG_PREFLIGHT_01 | [JSON final](../../outputs/feature04/AMP_RAG_PREFLIGHT_01_METRICAS_V2/metricas.json) | 78 casos, 312 prompts, zero tentativas |

No dry-run: TRV=0, TRI=0, TPF=0,5, TFF=0,5, TNINI=1 e TAP=1, somente na população simulada. As taxas reais são nulas. No preflight, todas as taxas de remediação são nulas; prompts não são tentativas de correção.

Os diretórios V1 publicados durante o desenvolvimento foram preservados como intermediários. V2 identifica a publicação final, com schema/política 1.0. Não houve sobrescrita pelo comando de publicação.

RRIS real é nula por ausência de evidência conjunta. TRV-P é nula por ausência de política de pesos. Suas fórmulas e leitores foram testados com fixtures válidas/inválidas, incluindo RRIS negativa e parsing limitado.

## Ambiente e comandos

Python 3.12.3 no ambiente `.venv` existente, biblioteca padrão e loaders compartilhados com PyYAML. Nenhuma dependência instalada nesta feature. Semgrep não foi executado.

```bash
make test-unit PYTHON=.venv/bin/python
.venv/bin/python scripts/reports/consolidate_metrics.py \
  --execucao AMP_DRY_01 \
  --entrada outputs/feature02/AMP_DRY_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --saida outputs/feature04/AMP_DRY_01_METRICAS_V2
.venv/bin/python scripts/reports/consolidate_metrics.py \
  --execucao AMP_RAG_PREFLIGHT_01 \
  --entrada outputs/feature03/AMP_RAG_PREFLIGHT_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --saida outputs/feature04/AMP_RAG_PREFLIGHT_01_METRICAS_V2
```

Essas saídas já existem: os comandos documentam a geração realizada e recusarão nova publicação no mesmo destino. Para reproduzir, selecionar uma saída nova. O comando histórico foi executado somente em cópias temporárias para conferir definições, tabelas, sessões e custos arquivados. O campo `simuladas=0`, já presente no calculador antes da extração, é adicional aos relatórios antigos; os campos originais conservaram os valores.

## Divergência preexistente e recuperação do perfil

Antes da implementação, `config/perfis/ampliado_v1/regras_remotas.yaml` já não correspondia ao hash do manifesto congelado. O teste inicial passou porque não validava esse arquivo oficial específico.

- Hash exigido: `80ddd8238a2ebeb10380cf2df3f9dd058584fe5ca179013987d7b9a4e6dead40`.
- Hash atual, preservado: `794380f23fad9ad82563fb95e74e0a579f7a9ff8f46d3730238d86e2b836d360`.
- Commit local com os bytes exatos recuperados: `6d90f347bacd8ef571dcec5c2b03cbe1ea6d9148`.

O [snapshot recuperado](../../outputs/feature04/preparacao/perfil_sast/perfil.json) conserva os IDs, conteúdo e hashes do perfil original. As regras locais também conferiram. A [evidência de recuperação](../../outputs/feature04/preparacao/recuperacao_perfil.json) registra os hashes e a origem no Git. Não houve alteração das regras atuais, do manifesto original ou das fontes arquivadas.

O leitor utiliza somente snapshot inteiramente verificável e registra o candidato atual divergente nos avisos e na proveniência. A publicação revalida ambos. Para próximos experimentos, selecionar o snapshot íntegro explicitamente em `--perfil-sast` ou tratar a divergência em tarefa separada; não usar o YAML atual como se ainda estivesse congelado.

## Semântica e cobertura dos testes

As taxas auxiliares ampliadas usam valores medidos; TRV mantém todas as tentativas da população. Proporções mínimas são suplementares. F desconhecido não representa falha funcional. A cadeia nova é delimitada pelo aceite original, enquanto o comando histórico preserva a análise retrospectiva.

Os testes cobrem números calculados manualmente, populações vazias, preflight, dry-run/P1L/cache, cadeia e pendências, dados inválidos, metadados ausentes, múltiplas CWEs, contratos 1.0/2.0, hashes/symlinks, custos desconhecidos, tempos paralelos, pesos, RRIS, CSV e CLI fora da raiz. A publicação foi testada com locks, falhas de escrita, fontes alteradas e destino criado no instante da promoção. Na plataforma Linux, a promoção exclusiva usa `renameat2(RENAME_NOREPLACE)`.

A validação de hashes de prompts respeita a ordem `role, content` usada pelo builder; o JSON arquivado ordena as chaves e não muda o texto efetivamente enviado.

## Evidências e hashes

- [Validação consolidada](../../outputs/feature04/validacao_entrega.json).
- [Hashes históricos capturados](../../outputs/feature04/preparacao/artefatos_historicos_sha256.json).
- [Manifesto dry-run](../../outputs/feature04/AMP_DRY_01_METRICAS_V2/manifesto.json).
- [Manifesto preflight](../../outputs/feature04/AMP_RAG_PREFLIGHT_01_METRICAS_V2/manifesto.json).

| Arquivo final | SHA-256 |
|---|---|
| AMP_DRY_01/metricas.json | `69a4a088b8707d52a27ffc562b7512d18ee7b48b33ced91ed7d883a38b889ae4` |
| AMP_DRY_01/manifesto.json | `8575bb211bee3e9f21c60b4a47130a54d5150ca09cccfd5fcae4a61d6b6723da` |
| AMP_RAG_PREFLIGHT_01/metricas.json | `dd2ec3270fa001c962f971273d6bd5241092dec3d5351690f7e7bdb0b88a4a67` |
| AMP_RAG_PREFLIGHT_01/manifesto.json | `764949ca30baf3232121591aa7a0f31e94c0c851a02d66156bf18e1d41184058` |

Os manifestos registram hashes de fontes, políticas e cada artefato exportado. Os relatórios não contêm timestamps de geração ou caminhos absolutos da máquina. Datas de sessões já arquivadas são dados observados, preservados como entrada.

## Limitações e continuidade

As métricas do dry-run verificam o funcionamento da análise; não avaliam a LLM. Preflight verifica preparação, não remediação. TCD é exploratório; não confirma sozinho o bloqueio de ataques. As estratégias alcançam populações diferentes pela parada sequencial, impedindo comparação causal direta das taxas.

A rastreabilidade histórica permanece limitada pelos artefatos ausentes, explicitamente reportados. Custos de chamadas sem registro não são inferidos. RRIS exige aplicação conjunta posterior, registro dos conflitos, scans comparáveis e resultado funcional. Nenhuma dessas etapas foi simulada como resultado real.

Próxima entrega: piloto de correções reais com orçamento/parâmetros definidos, perfil íntegro e cobertura funcional/dinâmica delimitada, utilizando esta consolidação para conferir cada tentativa.


## Sanitização do snapshot para publicação

O snapshot remoto contém um exemplo de webhook Slack em `pattern-not` que o GitHub
bloqueia como segredo. O domínio desse exemplo foi substituído por
`hooks.slack.example.invalid`. O sidecar `regras_remotas.yaml.sanitizacao.json`
registra os hashes anterior e sanitizado e a única substituição permitida.
O leitor verifica o arquivo sanitizado, reconstrói os bytes históricos em memória
e verifica o hash exigido pelo manifesto original. Alterações extras são rejeitadas.
Os contratos, o manifesto e as métricas arquivadas conservam seus hashes históricos;
novas consolidações registram o arquivo sanitizado, seu sidecar e um aviso de sanitização.
Para executar novos scans, utilize um perfil novo, pois o YAML publicado está sanitizado.
