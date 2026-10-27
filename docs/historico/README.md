# Histórico da organização do repositório

## Reorganização de 26/10/2026

Só documentação e a interface do painel mudaram de lugar. Código, configurações, testes, regras e
resultados ficaram onde estavam, porque o baseline oficial, a referência Docker, os contratos das
execuções e os próprios resultados apontam para esses caminhos. A explicação completa está em
`src/pipeline/README.md` (seção "Por que os módulos não mudam de nome nem de pasta") e em
`config/README.md`.

Registros antigos em `outputs/` e alguns relatórios de auditoria continuam citando os caminhos antigos;
eles não são editados. Use esta tabela para encontrar o arquivo atual.

| Caminho antigo | Caminho atual |
|---|---|
| `README.md` (versão até 26/10/2026) | `docs/guias/referencia_detalhada.md` (a raiz tem um README novo, curto) |
| `features/` | `docs/historico/features/` |
| `frontend/painel/` | `src/pipeline/painel/web/` |
| `docs/painel_local.md` | `docs/guias/painel_local.md` |
| `docs/modelo_colab.md` | `docs/guias/modelo_colab.md` |
| `docs/piloto_10_issues.md` | `docs/guias/piloto_10_issues.md` |
| `docs/validacao_baseline_docker.md` | `docs/guias/validacao_baseline_docker.md` |
| `docs/GUIA_CONTINUIDADE_TCC2.md` | `docs/planejamento/GUIA_CONTINUIDADE_TCC2.md` |
| `docs/estrutura_projeto.md` | `docs/historico/estrutura_projeto.md` |

Arquivos novos: `README.md` (curto), `docs/README.md`, `src/pipeline/README.md`, `scripts/README.md`,
`config/README.md`, `outputs/README.md` e este arquivo.

## `features/`

As features 01–07 foram os incrementos de desenvolvimento entre 12/10 e 18/10/2026. Cada pasta tem o
pedido (`README.md`) e o relatório de entrega (`ENTREGA.md`); as evidências estão em
`outputs/feature02/` … `outputs/feature07/`.

| Feature | Assunto |
|---|---|
| 01 | Catálogo ampliado de 78 casos por ocorrência |
| 02 | Integração do catálogo ao pipeline: perfil local, preflight e contrato |
| 03 | RAG simplificado e prompts P3/P4 |
| 04 | Consolidação verificável das métricas |
| 05 | Otimização da validação (mapa de testes, cache, benchmark) |
| 06 | Cobertura funcional revisada dos 78 casos (`relacionada_v2`) |
| 07 | Modelo Qwen hospedado no Colab |

## Reorganização do código — 26/10/2026

O código passou a seguir a arquitetura de dutos e filtros também nas pastas: uma pasta por etapa em
`src/pipeline/etapas/`, além de `orquestracao/`, `comum/`, `painel/` e `legado/`. Os scripts ganharam pastas e
nomes em português. Nenhuma função, classe ou lógica mudou; só nomes de arquivos, pastas, imports e os nomes de
arquivo usados nas identidades. Como o nome e o conteúdo de parte desses módulos entram na identidade científica,
o baseline e a referência Docker foram gerados de novo (`outputs/baselines/docker/oficial_v2/`); a referência
anterior está em `docker/historico/referencia_oficial_v1.json`. A verificação antes × depois está em
`outputs/revalidacoes/REORGANIZACAO_20261026/`.

### Módulos (`src/pipeline/`)

| Antes | Agora |
|---|---|
| `src/pipeline/caminhos.py` | `src/pipeline/comum/caminhos.py` |
| `src/pipeline/catalogo.py` | `src/pipeline/etapas/e02_catalogo/catalogo.py` |
| `src/pipeline/execucao_ampliada.py` | `src/pipeline/orquestracao/preflight.py` |
| `src/pipeline/llm/colab_client.py` | `src/pipeline/etapas/e05_geracao_llm/cliente_colab.py` |
| `src/pipeline/llm/colab_protocol.py` | `src/pipeline/etapas/e05_geracao_llm/protocolo_colab.py` |
| `src/pipeline/llm/falso.py` | `src/pipeline/etapas/e05_geracao_llm/resposta_simulada.py` |
| `src/pipeline/llm/openai_client.py` | `src/pipeline/etapas/e05_geracao_llm/cliente_openai.py` |
| `src/pipeline/llm/provider.py` | `src/pipeline/etapas/e05_geracao_llm/provedor.py` |
| `src/pipeline/llm/schema.py` | `src/pipeline/etapas/e05_geracao_llm/esquema.py` |
| `src/pipeline/metrics/__init__.py` | `src/pipeline/etapas/e09_metricas/__init__.py` |
| `src/pipeline/metrics/calculator.py` | `src/pipeline/etapas/e09_metricas/calculo.py` |
| `src/pipeline/metrics/exporter.py` | `src/pipeline/etapas/e09_metricas/publicacao.py` |
| `src/pipeline/metrics/loader.py` | `src/pipeline/etapas/e09_metricas/leitura.py` |
| `src/pipeline/metrics/normalizer.py` | `src/pipeline/etapas/e09_metricas/normalizacao.py` |
| `src/pipeline/metrics/rris.py` | `src/pipeline/etapas/e09_metricas/rris.py` |
| `src/pipeline/painel/controller.py` | `src/pipeline/painel/controle.py` |
| `src/pipeline/painel/server.py` | `src/pipeline/painel/servidor.py` |
| `src/pipeline/patching/applier.py` | `src/pipeline/etapas/e06_aplicacao/aplicador.py` |
| `src/pipeline/patching/indentacao.py` | `src/pipeline/etapas/e06_aplicacao/indentacao.py` |
| `src/pipeline/prompts/builder.py` | `src/pipeline/etapas/e04_prompt/montagem.py` |
| `src/pipeline/rag/__init__.py` | `src/pipeline/etapas/e03_contexto_rag/__init__.py` |
| `src/pipeline/rag/retriever.py` | `src/pipeline/etapas/e03_contexto_rag/recuperacao.py` |
| `src/pipeline/registro.py` | `src/pipeline/etapas/e08_registro/registro.py` |
| `src/pipeline/run_pipeline.py` | `src/pipeline/orquestracao/campanha.py` |
| `src/pipeline/sast/associacoes.py` | `src/pipeline/etapas/e02_catalogo/associacoes.py` |
| `src/pipeline/sast/comparacao.py` | `src/pipeline/legado/comparacao_v1.py` |
| `src/pipeline/sast/comparacao_v2.py` | `src/pipeline/etapas/e01_analise_sast/comparacao.py` |
| `src/pipeline/sast/estrutura.cjs` | `src/pipeline/etapas/e01_analise_sast/estrutura.cjs` |
| `src/pipeline/sast/estrutura.py` | `src/pipeline/etapas/e01_analise_sast/estrutura.py` |
| `src/pipeline/sast/filtro.py` | `src/pipeline/legado/filtro.py` |
| `src/pipeline/sast/perfil.py` | `src/pipeline/etapas/e01_analise_sast/perfil.py` |
| `src/pipeline/sast/semgrep_client.py` | `src/pipeline/etapas/e01_analise_sast/semgrep.py` |
| `src/pipeline/target/workspace.py` | `src/pipeline/etapas/e06_aplicacao/worktrees.py` |
| `src/pipeline/validation/cache.py` | `src/pipeline/etapas/e07_validacao/cache.py` |
| `src/pipeline/validation/components.py` | `src/pipeline/comum/componentes.py` |
| `src/pipeline/validation/conjunto_d.py` | `src/pipeline/etapas/e07_validacao/conjunto_d.py` |
| `src/pipeline/validation/coverage.py` | `src/pipeline/etapas/e07_validacao/cobertura.py` |
| `src/pipeline/validation/coverage_api_setup.mjs` | `src/pipeline/etapas/e07_validacao/preparo_api_cobertura.mjs` |
| `src/pipeline/validation/coverage_audit.py` | `src/pipeline/etapas/e07_validacao/auditoria_cobertura.py` |
| `src/pipeline/validation/coverage_runner.py` | `src/pipeline/etapas/e07_validacao/execucao_cobertura.py` |
| `src/pipeline/validation/engine.py` | `src/pipeline/etapas/e07_validacao/medicao.py` |
| `src/pipeline/validation/identity.py` | `src/pipeline/comum/identidade.py` |
| `src/pipeline/validation/policy.py` | `src/pipeline/etapas/e07_validacao/politicas.py` |
| `src/pipeline/validation/preparacao_api.py` | `src/pipeline/etapas/e07_validacao/preparacao_api.py` |
| `src/pipeline/validation/retry.py` | `src/pipeline/etapas/e07_validacao/repeticao.py` |
| `src/pipeline/validation/runner.py` | `src/pipeline/etapas/e07_validacao/camadas.py` |
| `src/pipeline/validation/selection.py` | `src/pipeline/etapas/e07_validacao/selecao.py` |

### Scripts (`scripts/`)

| Antes | Agora |
|---|---|
| `scripts/audit/audit_functional_coverage.py` | `scripts/auditoria/auditar_cobertura_funcional.py` |
| `scripts/audit/audit_semgrep_coverage.py` | `scripts/auditoria/auditar_cobertura_semgrep.py` |
| `scripts/audit/build_challenge_matrix.py` | `scripts/auditoria/gerar_matriz_desafios.py` |
| `scripts/audit/build_repair_candidates.py` | `scripts/auditoria/gerar_candidatos_correcao.py` |
| `scripts/audit/build_sast_profile.py` | `scripts/auditoria/congelar_perfil_sast.py` |
| `scripts/audit/classify_combined_scan.py` | `scripts/auditoria/classificar_scan_combinado.py` |
| `scripts/audit/compare_functional_baselines.py` | `scripts/auditoria/comparar_baselines_funcionais.py` |
| `scripts/audit/evaluate_reference_fixes.py` | `scripts/auditoria/avaliar_codefixes.py` |
| `scripts/audit/recompare_archived_scans.py` | `scripts/auditoria/recomparar_scans_arquivados.py` |
| `scripts/audit/review_associations.py` | `scripts/auditoria/revisar_associacoes.py` |
| `scripts/audit/scan_semgrep_exploratorio.py` | `scripts/auditoria/scan_semgrep_exploratorio.py` |
| `scripts/audit/test_rodada.py` | `scripts/auditoria/testar_rodada.py` |
| `scripts/audit/verify_rodada10.py` | `scripts/auditoria/verificar_rodada10.py` |
| `scripts/audit/verify_rodada11.py` | `scripts/auditoria/verificar_rodada11.py` |
| `scripts/audit/verify_rodada12.py` | `scripts/auditoria/verificar_rodada12.py` |
| `scripts/audit/verify_rodada8.py` | `scripts/auditoria/verificar_rodada8.py` |
| `scripts/audit/verify_rodada9.py` | `scripts/auditoria/verificar_rodada9.py` |
| `scripts/experiment/baseline_testes.py` | `scripts/experimento/gerar_linha_de_base_historica.py` |
| `scripts/experiment/benchmark_validation.py` | `scripts/experimento/replay_patches.py` |
| `scripts/experiment/build_expanded_catalog.py` | `scripts/experimento/gerar_catalogo_ampliado.py` |
| `scripts/experiment/build_issue_catalog.py` | `scripts/experimento/gerar_catalogo_historico.py` |
| `scripts/experiment/diagnose_llm.py` | `scripts/experimento/diagnosticar_llm.py` |
| `scripts/experiment/gerar_conjunto_d.py` | `scripts/experimento/gerar_conjunto_d.py` |
| `scripts/experiment/mark_juiceshop_challenges.py` | `scripts/experimento/marcar_desafios_historicos.py` |
| `scripts/experiment/measure_validation_cost.py` | `scripts/experimento/medir_custo_validacao.py` |
| `scripts/experiment/replay_anchor_application.py` | `scripts/experimento/replay_ancoras.py` |
| `scripts/experiment/sondagem_sast.py` | `scripts/experimento/sondagem_sast.py` |
| `scripts/experiment/try_one.py` | `scripts/experimento/tentar_um_caso.py` |
| `scripts/experiment/validate_functional_coverage.py` | `scripts/experimento/gerar_baseline_funcional.py` |
| `scripts/experiment/validate_knowledge_base.py` | `scripts/experimento/validar_base_rag.py` |
| `scripts/experiment/validate_runner_scenarios.py` | `scripts/experimento/validar_cenarios_camadas.py` |
| `scripts/reports/consolidate_metrics.py` | `scripts/relatorios/consolidar_metricas.py` |
| `scripts/reports/metricas_execucao.py` | `scripts/relatorios/metricas_historicas.py` |
| `scripts/reports/report_baseline.py` | `scripts/relatorios/relatorio_baseline_historico.py` |
| `scripts/reports/report_patch_revalidation.py` | `scripts/relatorios/relatorio_revalidacao.py` |
| `scripts/reports/report_rodada10.py` | `scripts/relatorios/relatorio_rodada10.py` |
| `scripts/reports/report_rodada11.py` | `scripts/relatorios/relatorio_rodada11.py` |
| `scripts/reports/report_rodada12.py` | `scripts/relatorios/relatorio_rodada12.py` |
| `scripts/reports/report_rodada2.py` | `scripts/relatorios/relatorio_rodada2.py` |
| `scripts/reports/report_rodada3.py` | `scripts/relatorios/relatorio_rodada3.py` |
| `scripts/reports/report_rodada4.py` | `scripts/relatorios/relatorio_rodada4.py` |
| `scripts/reports/report_rodada5.py` | `scripts/relatorios/relatorio_rodada5.py` |
| `scripts/reports/report_rodada6.py` | `scripts/relatorios/relatorio_rodada6.py` |
| `scripts/reports/report_rodada7.py` | `scripts/relatorios/relatorio_rodada7.py` |
| `scripts/reports/report_rodada8.py` | `scripts/relatorios/relatorio_rodada8.py` |
| `scripts/reports/report_rodada9.py` | `scripts/relatorios/relatorio_rodada9.py` |
| `scripts/reports/report_validation_benchmark.py` | `scripts/relatorios/relatorio_replays.py` |
| `scripts/setup/prepare_api_worktrees.py` | `scripts/preparacao/preparar_worktrees_api.py` |
| `scripts/setup/setup_target.sh` | `scripts/preparacao/preparar_alvo.sh` |

Nomes de módulo com ponto seguem o mesmo mapa: `pipeline.run_pipeline` → `pipeline.orquestracao.campanha`,
`pipeline.validation.runner` → `pipeline.etapas.e07_validacao.camadas`, e assim por diante.
