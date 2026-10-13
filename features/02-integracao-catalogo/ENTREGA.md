# Entrega da feature 02 — Integração do catálogo ampliado

**Data:** 12/10/2026.  
**Status:** implementada e validada, com limites de cobertura documentados.  
**Publicação:** alterações locais; sem commit, push ou chamadas à LLM.

## Resultados

- Perfil SAST local congelado e gate reproduzindo exatamente **78 ocorrências**, sem ausentes ou adicionais.
- Preflight real completo com **78 casos e 156 prompts P1/P2**; sem patches ou cliente LLM.
- Dry-run real com dois casos JS/TS: patch aplicado, scan global, comparação, validação e registro.
- Retomada compatível reconheceu as duas tentativas concluídas e não repetiu nenhuma.
- **94 testes unitários passaram**, sendo 21 novos nesta feature e 73 preexistentes.
- **273 artefatos históricos** conservaram seus hashes. Os checkouts de validação e da feature 01 ficaram limpos.
- Custo de API **US$ 0**: duas tentativas simuladas, zero chamadas reais.

## Ambiente e dependências

Python 3.12.3, Node v24.14.0, npm 11.9.0 e Semgrep 1.177.0.
Foi criado um ambiente completo em `.venv`; a lista efetiva de dependências está em
[python-freeze.txt](../../outputs/feature02/preparacao/python-freeze.txt).

`workspace/wt-1` é uma worktree detached no commit
`f915bddd82790d0f3018902d36ae9b4241a5f51f`, preparada a partir do repositório local
`workspace/catalogo-alvo` sem alterar os fontes do checkout da feature 01.

**Diferença constatada no plano:** o commit fixado não inclui `package-lock.json` raiz
e contém `package-lock=false` em `.npmrc`. Por isso, a tentativa inicial de `npm ci`
não pôde instalar. Foi gerado um lock de preparação com
`npm install --package-lock-only --package-lock=true --ignore-scripts`, seguido de
`CYPRESS_INSTALL_BINARY=0 npm ci --package-lock=true --no-audit --no-fund`.
O [lock utilizado](../../outputs/feature02/preparacao/package-lock-gerado.json) foi arquivado.
Esse lock representa resolução atual das dependências, não um lock oficial histórico.
O postinstall também instalou e compilou o frontend; suas dependências não constituem
um snapshot oficial antigo. A comparação funcional usa a referência medida neste ambiente.

## Regras congeladas

A exportação foi obtida por `ConfigLoader("p/default").load_config()` do Semgrep 1.177.0,
e arquivada em [p-default-exportado.yaml](../../outputs/feature02/preparacao/p-default-exportado.yaml).
O builder reuniu as regras locais e preservou IDs, flags, hashes e exclusões.

- [Manifesto do perfil](../../config/perfis/ampliado_v1/perfil.json).
- [Regras remotas](../../config/perfis/ampliado_v1/regras_remotas.yaml).
- [Regras locais](../../config/perfis/ampliado_v1/regras_locais.yaml).
- [Relatório de reprodução](../../outputs/feature02/AMP_PREFLIGHT_01/sast_antes/reproducao.json).

A exportação foi obtida depois da auditoria. A igualdade de findings confirma reprodução
dos 78 casos, mas não prova identidade integral das regras com o conteúdo remoto anterior
que não foi arquivado. A versão congelada é o instrumento desta nova execução.

## Comandos utilizados

```bash
.venv/bin/python scripts/audit/build_sast_profile.py \
  --regras-remotas outputs/feature02/preparacao/p-default-exportado.yaml \
  --saida config/perfis/ampliado_v1

PYTHONPATH=src .venv/bin/python -m pipeline.run_pipeline \
  --execucao AMP_PREFLIGHT_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --perfil-sast config/perfis/ampliado_v1/perfil.json \
  --saida outputs/feature02/AMP_PREFLIGHT_01 \
  --estrategias P1,P2 --somente-preflight --k 1 \
  --semgrep-bin .venv/bin/semgrep

.venv/bin/python scripts/experiment/baseline_testes.py \
  --commit f915bddd82790d0f3018902d36ae9b4241a5f51f \
  --saida outputs/feature02/validacao/baseline_testes.json

PYTHONPATH=src .venv/bin/python -m pipeline.run_pipeline \
  --execucao AMP_DRY_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --perfil-sast config/perfis/ampliado_v1/perfil.json \
  --saida outputs/feature02/AMP_DRY_01 \
  --estrategias P1 --casos AMPfb154534099cb3ca,AMP95adf572d3c6677f \
  --dry-run --k 1 --semgrep-bin .venv/bin/semgrep \
  --baseline-testes outputs/feature02/validacao/baseline_testes.json
```

A retomada repetiu o último comando com `--pular-checagem-ambiente`, mantendo gate,
contrato e hashes obrigatórios. Havia exatamente dois registros antes e depois.
Métricas foram calculadas com `scripts/reports/metricas_execucao.py AMP_DRY_01
--saida outputs/feature02/AMP_DRY_01`.

## Evidências e interpretação do dry-run

[Referência funcional](../../outputs/feature02/validacao/baseline_testes.json):
T3 sem falhas e T4 com falha preexistente do recurso StackOverflow (HTTP 403).
O checker sem patch aprovou o ambiente usando essa referência.

| Caso | Arquivo | R | F | M | Aplicação |
|---|---|---:|---:|---:|---|
| `AMP95adf572d3c6677f` | `routes/keyServer.ts` | 0 | 1 | 1 | aplicado |
| `AMPfb154534099cb3ca` | `routes/login.ts` | 0 | 0 | 1 | aplicado |

A simulação só inseriu comentários; R=0 era esperado e nenhum resultado foi tratado como
correção de vulnerabilidade. O login teve F=0 porque o teste
`test/api/vuln-code-snippet.test.ts` exige exatamente a linha 15 no hint do desafio,
mas a inserção deslocou a referência para a linha 16. A falha persistiu nas duas rodadas
e foi preservada. Também houve uma falha intermitente de rede no PasteBin, registrada
pelo runner. Não se alterou F/D nem se removeu teste para fazer a simulação passar.

Esse resultado confirma que o pipeline aplica a escada de validação e rejeita mudanças
que quebram as asserções existentes. Não confirma que todo comentário seja funcionalmente
inofensivo. A worktree foi restaurada ao final.

[Registros](../../outputs/feature02/AMP_DRY_01/resultados_consolidados/execucoes.jsonl),
[métricas](../../outputs/feature02/AMP_DRY_01/resultados_consolidados/AMP_DRY_01_metricas.json)
e [histórico de sessões](../../outputs/feature02/AMP_DRY_01/resultados_consolidados/AMP_DRY_01_sessoes.json)
contêm os caminhos das comparações, testes, diffs e respostas simuladas.

### Tempos observados

- `AMP95adf572d3c6677f`: SAST global 53.51 s; validação funcional 81.03 s.
- `AMPfb154534099cb3ca`: SAST global 53.49 s; validação funcional 218.64 s.

Esses tempos medem esta máquina/ambiente e não substituem estimativa do experimento final.

## Identidade, parsing e retomada

A assinatura AMP identifica o baseline; a comparação posterior usa blocos de linhas únicos
para traduzir posições. Ambiguidades resultam em R/M nulos, sem aceite automático.
Avisos de parsing antigos, iguais e em arquivos não alterados são cobertura limitada;
novos problemas ou arquivos alterados afetam a conclusão. Scans globais e relatórios
preservam essas evidências.

Contratos bloqueiam troca de catálogo, regras, estratégias, casos, referência funcional
ou templates na mesma saída. Hashes dos artefatos concluídos são conferidos antes da retomada.
Registros corrompidos/incompletos não são ignorados silenciosamente no modo ampliado.

## Hashes de referência

| Fonte/artefato | SHA-256 |
|---|---|
| `config/perfis/ampliado_v1/perfil.json` | `2b12520e0ccfcce62b967834b16d1b7e21683953c1d349822010ddaf67cbfa2c` |
| `outputs/feature02/preparacao/p-default-exportado.yaml` | `278f7da1e2b40088ca8e1af787611138d00dfa4267b28e4efc73c203faec87cc` |
| `outputs/feature02/AMP_PREFLIGHT_01/contrato_execucao.json` | `5b9da6c8b6b2b6eb0b16a88bd801d99104bb68c352ca84152c732a0333554586` |
| `outputs/feature02/AMP_DRY_01/contrato_execucao.json` | `88be74f7919cf7826b46d766a7e2488d4c1412e5db50aa8d6ad3561187eb91bc` |
| `outputs/feature02/validacao/baseline_testes.json` | `9e1415de5d70339920f09bf661f72b876f53ebbbffd58ea00c5e4c354a838d28` |
| `outputs/feature02/preparacao/package-lock-gerado.json` | `e244b84f2190ff552de2a957da896c60a73d54dba10f0f231311316673a1978a` |

## Continuação

P3/P4 e os oráculos adicionais permanecem pendentes. F corresponde à suíte de servidor/API
atual; casos de frontend ainda precisam de validação específica antes das conclusões finais.
Não houve execução real das 78 correções nem avaliação consolidada de RRIS.
