# Correção da validação do piloto com dez issues

Execução original: `AMP_PAINEL_20261017T064627Z_bf4efba0`.
Data: 17/10/2026. Os registros, respostas, patches e métricas originais foram
preservados. A revalidação é diagnóstico dos mesmos patches, sem nova geração LLM.

## Problema confirmado

`wt-3` e `wt-4` tinham código e dependências, mas não os builds ignorados pelo Git.
O preflight antigo verificava commit, fontes, dependências e baseline, sem exigir
esses arquivos de inicialização da API.

Em 14 tentativas, houve `Exiting due to unsatisfied precondition!`. Em 13 delas,
um testcase sintético de falha do arquivo, com nome vazio após `arquivo ::`, foi
classificado como reprovação funcional. F=0 ficou registrado sem as asserções
esperadas terem sido executadas. O erro também podia ocorrer somente na repetição.

Outro problema era temporal: importar `server.ts` inicia a verificação assíncrona
de pré-condições. `--test-force-exit` podia encerrar o processo antes de ela terminar.
Uma rodada aparentemente aprovada não garantia inicialização validada.

## Correções

1. `preparacao_api.py` inventaria `build/server.js`, os quatro entrypoints
   frontend e os chunks `hacking-instructor-*.js`. Recusa arquivos ausentes,
   vazios, escapes de caminho e porta ocupada. Os hashes integram o ambiente
   funcional da nova política, baseline e cache.
2. `prepare_api_worktrees.py` exige commit e fontes limpas, copia árvores
   ausentes de uma referência preparada, com arquivos isolados e publicação
   exclusiva. Não substitui conteúdo desconhecido divergente. Não instala pacotes.
3. O preflight da política `relacionada_v2` exige essas condições antes do cliente
   LLM e da publicação do contrato; continua sem executar testes ou iniciar serviços.
4. `coverage_api_setup.mjs` aguarda `preconditionsReady` antes da descoberta dos
   testes, após os preloads existentes de ambiente e TypeScript. Assim o force-exit
   não esconde uma verificação de startup ainda em andamento.
5. JUnit de arquivo sem identidade de teste é falha operacional. Grupos com
   carregamento inválido, timeout ou seleção incompleta não fornecem reprovação
   a nenhuma das três definições de F. Sem evidência suficiente, F fica nulo.
   Reprovações comprovadas de compilação ou de outros grupos íntegros continuam F=0.
6. As identidades dos adaptadores e do cache mudaram. Evidência funcional antiga
   não é reutilizada como se fosse uma medição corrigida.

O comparador SAST, catálogo, prompts, conjunto D, suas três definições F/D e a
parada da cadeia não foram alterados. R/M continuam medidos independentemente de F.

## Evidências novas

Raiz: [PILOTO10_CORRECAO_V1](../../outputs/revalidacoes/PILOTO10_CORRECAO_V1/).

- [Baseline novo](../../outputs/revalidacoes/PILOTO10_CORRECAO_V1/BASELINE/baseline_testes.json):
  39 grupos, 484 testes aprovados e seis ignorados, compilações aprovadas.
- [Smoke na wt-4](../../outputs/revalidacoes/PILOTO10_CORRECAO_V1/SMOKE_WT4/baseline_testes.json):
  grupos `current_user`, `key` e `track`, com 53 testes aprovados. Demonstra a
  execução real nas condições que antes falhavam.
- [Replay](../../outputs/revalidacoes/PILOTO10_CORRECAO_V1/REPLAY_K4/manifesto.json):
  patches aplicados isoladamente, K=4, SAST global e validação funcional, sem LLM.
- [Comparação](../../outputs/revalidacoes/PILOTO10_CORRECAO_V1/COMPARACAO/comparacao.csv)
  e [resumo](../../outputs/revalidacoes/PILOTO10_CORRECAO_V1/COMPARACAO/resumo.json):
  identidades e hashes dos mesmos patches, R/F/M originais e revalidados.
- [Verificação de integridade](../../outputs/revalidacoes/PILOTO10_CORRECAO_V1/verificacao.json):
  hashes históricos, custo/chamadas LLM inalterados, testes unitários e limpeza.

O benchmark aceita `--revalidacao` explicitamente para usar baseline novo em uma
saída de diagnóstico sob `outputs/revalidacoes/`. O modo anterior continua exigindo
o baseline da origem. A origem e seus hashes são validados pelo leitor de métricas;
o relatório exige correspondência exata das populações e evidências.

## Resultado da revalidação

| Indicador | Resultado |
|---|---:|
| Patches revalidados / respostas sem patch | 37 / 3 |
| Tentativas com falha operacional: origem → revalidação | 14 → 0 |
| Patches com F_criterio alterado | 12 |
| Patches com R/M alterados | 0 |
| Patches aceitos por R/F_criterio/M | 11, em quatro casos |
| Rejeitados por R1/F0/M1 | 12 |
| Rejeitados por R0/F0/M1 | 7 |
| Rejeitados por R0/F1/M1 | 6 |
| Indeterminados SAST | 1 |
| F_criterio indeterminado após revalidação | 0 |

Os quatro casos com algum patch aceito são `login`, `trackOrder`, `currentUser`
e `deluxe`. Os 11 aceites são resultados dos patches já existentes, medidos no
alcance funcional revisado e segundo o conjunto D vigente; não são 11 issues.

As rejeições de `currentUser` P1/P2, por exemplo, agora possuem asserção real:
o teste espera conseguir retornar senha usando o parâmetro `fields`. Essa
classificação F/D foi preservada e merece revisão metodológica própria. Não se
alterou a classificação depois de observar a correção. Os erros TypeScript e
as falhas XML de expansão interna também continuam registrados como reprovações.

O comparador manteve a indeterminação de `likeProductReviews` P2; a correção de
startup não implica resolver ambiguidades SAST. O replay durou aproximadamente
12min22s, excluindo sua preparação inicial, sem afirmar ganho causal de desempenho.

A suíte Python passou de 258 testes iniciais para 266, incluindo regressões para
sentinela de arquivo, falha de pré-condição, gate com builds ausentes, artefato
alterado e porta ocupada. A comparação foi publicada novamente em outro destino
para conferir determinismo. O preflight final confirmou dez casos, 40 prompts e
quatro worktrees, sem LLM. A auditoria atualizada mantém 52 casos preparados e
26 bloqueados; a campanha completa segue pendente.

## Reprodução

Todos os destinos abaixo já pertencem à entrega; para repetir, use outra raiz de
saída e atualize a referência do baseline. Não sobrescrever evidências existentes.

```bash
.venv/bin/python scripts/setup/prepare_api_worktrees.py \
  --origem workspace/wt-1 --k 4

.venv/bin/python scripts/experiment/validate_functional_coverage.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 --mapa-testes config/mapa_testes_relacionados_v2.yaml \
  --revisao config/cobertura_funcional_v1.yaml \
  --saida outputs/revalidacoes/PILOTO10_CORRECAO_V1/BASELINE

.venv/bin/python scripts/experiment/benchmark_validation.py --revalidacao \
  --origem outputs/execucoes/AMP_PAINEL_20261017T064627Z_bf4efba0 \
  --saida outputs/revalidacoes/PILOTO10_CORRECAO_V1/REPLAY_K4 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --baseline-testes outputs/revalidacoes/PILOTO10_CORRECAO_V1/BASELINE/baseline_testes.json \
  --k 4 --politica-validacao relacionada_v2 \
  --mapa-testes config/mapa_testes_relacionados_v2.yaml \
  --cobertura-funcional config/cobertura_funcional_v1.yaml \
  --cache-validacao desligado --repeticao-api ampla

.venv/bin/python scripts/reports/report_patch_revalidation.py \
  --origem outputs/execucoes/AMP_PAINEL_20261017T064627Z_bf4efba0 \
  --replay outputs/revalidacoes/PILOTO10_CORRECAO_V1/REPLAY_K4 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --saida outputs/revalidacoes/PILOTO10_CORRECAO_V1/COMPARACAO
```

## Interpretação e limites

São 37 patches revalidáveis entre 40 registros de origem. Três respostas tiveram
âncora ausente e não produziram patch; não foram transformadas em novos resultados.
O replay mede todos os patches arquivados e não aplica novamente a parada da cadeia.
Seus aceites não são uma nova taxa de sucesso de geração, nem efeito causal de RAG.

O conjunto D foi mantido. Asserções que exigem comportamentos vulneráveis e ainda
são classificadas como F permanecem uma limitação a revisar separadamente, com
critérios prévios. Não foram reclassificadas para favorecer os patches observados.
O teste normal pode passar e o comparador continuar indeterminado; não se força R/M.

Os tempos incluem verificações que antes podiam ser interrompidas. Não atribuir a
diferença temporal apenas a K=4, nem apresentar suites que abortaram como validação
mais rápida. A inicialização do alvo mantém as consultas opcionais de disponibilidade
já existentes, sem geração/cobrança LLM pelo pipeline.

Os YAMLs de execução apontam para o baseline novo. Contratos anteriores permanecem
consultáveis; retomadas com implementação ou baseline divergentes são recusadas.
