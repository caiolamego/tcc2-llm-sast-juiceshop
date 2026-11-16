# Comandos avulsos (`scripts/`)

Comandos executados à mão, fora do fluxo automático do `executar.py`. Rode-os a partir da raiz do
repositório, de preferência dentro do container (`docker compose run --rm tcc python scripts/...`). Todos
aceitam `--help`.

Situação: **núcleo** (usado na campanha atual), **apoio** (diagnóstico e verificação), **legado** (modo
histórico E01–E03 ou preparação anterior ao Docker), **exploratório** (auditoria das regras do Semgrep).

Os nomes atuais valem desde 26/10/2026. Registros antigos em `outputs/` e relatórios de auditoria citam os
nomes anteriores (`scripts/experiment/...`, `scripts/audit/...`); a correspondência está em
`docs/historico/README.md`.

Em 01/11/2026 saíram os scripts que só serviam ao modo histórico: `gerar_catalogo_historico.py`,
`marcar_desafios_historicos.py`, `validar_cenarios_camadas.py`, `medir_custo_validacao.py` e
`relatorio_baseline_historico.py`. Eles continuam na tag git `modo-historico-final`
(`git show modo-historico-final:scripts/experimento/<nome>.py`).

## `preparacao/` — preparação do alvo

| Script | Para que serve | Situação |
|---|---|---|
| `preparar_alvo.sh` | Prepara o Juice Shop fora do Docker (clone, worktrees, `npm install`). Substituído por `make docker-setup`. | legado |
| `preparar_worktrees_api.py` | Copia os builds de uma worktree para as outras, fora do Docker. | legado |

## `experimento/` — experimento

| Script | Para que serve | Situação |
|---|---|---|
| `gerar_catalogo_ampliado.py` | Gera o catálogo de 78 casos por ocorrência a partir das evidências arquivadas. | núcleo |
| `gerar_baseline_funcional.py` | Gera o baseline funcional (régua do critério F) e roda os controles de regressão. Chamado por `make docker-baseline`. | núcleo |
| `validar_controles_cobertura.py` | Executa controles declarados em JSON, exige aprovação do código original e falha do teste esperado no mutante, restaura os bytes e publica evidências sem LLM. | apoio |
| `gerar_conjunto_d.py` | Gera `config/conjunto_d.json` e `docs/conjunto_d.md` a partir dos critérios. | núcleo |
| `gerar_conjunto_d_v3.py` | Gera a versão vigente do conjunto D (critério (e) e ampliação do (d)), a revisão de cobertura v8 e o mapa v9. Não sobrescreve arquivos. |
| `gerar_conjunto_d_por_caso.py` | Gera a versão do conjunto D com o critério (d), ligada a casos, com a revisão de cobertura e o mapa correspondentes. Não sobrescreve arquivos. |
| `avaliacao_conjunta_rris.py` | Aplica juntos os patches aceitos de uma execução e gera a evidência da RRIS. Roda no Docker, com a trava das worktrees, sem LLM. |
| `replay_patches.py` | Replay de patches arquivados com SAST e testes reais, sem LLM (`--revalidacao`). | apoio |
| `replay_ancoras.py` | Reaplica respostas com âncora ausente em cópias temporárias. | apoio |
| `diagnosticar_llm.py` | Diagnóstico da LLM: offline, conexão, mensagem curta ou prompt arquivado. | apoio |
| `validar_base_rag.py` | Valida a base RAG ou publica um manifesto novo. | apoio |
| `tentar_um_caso.py` | Uma tentativa ponta a ponta sobre um caso: o orquestrador com um caso, uma estratégia e K=1. | apoio |
| `sondagem_sast.py` | Sondagem do oráculo R com um patch dado, sem LLM (`preflight.sondar`). | apoio |
| `gerar_linha_de_base_historica.py` | Linha de base de testes `outputs/baseline_testes.json`, padrão de `camadas.py` e de `--baseline-testes`. | legado |

## `relatorios/` — relatórios e métricas

| Script | Para que serve | Situação |
|---|---|---|
| `consolidar_metricas.py` | Consolida as métricas de uma execução em JSON e CSV (chamado pelo `executar.py`). | núcleo |
| `comparar_modelos.py` | Compara execuções de modelos diferentes a partir das métricas publicadas, com pares de casos e estratégias em comum. |
| `relatorio_revalidacao.py` | Compara uma revalidação sem LLM com os registros originais. | apoio |
| `relatorio_replays.py` | Compara replays concluídos. | apoio |
| `metricas_historicas.py` | Métricas do modo histórico (E01, E02) nas três definições de F; os testes o usam para conferir os números arquivados. | legado |
| `relatorio_rodada2.py` … `relatorio_rodada12.py` | Um relatório por rodada da auditoria de regras. | exploratório |

## `auditoria/` — auditoria das regras e das referências

| Script | Para que serve | Situação |
|---|---|---|
| `congelar_perfil_sast.py` | Congela regras locais e remotas num perfil verificável (`config/perfis/`). | núcleo |
| `comparar_baselines_funcionais.py` | Compara dois baselines funcionais grupo a grupo. Usado por `make docker-baseline`. | núcleo |
| `auditar_cobertura_funcional.py` | Audita a cobertura funcional por ocorrência. | apoio |
| `scan_semgrep_exploratorio.py` | Roda perfis exploratórios sem alterar o catálogo oficial. | exploratório |
| `auditar_cobertura_semgrep.py` | Compara scans exploratórios com o baseline congelado. | exploratório |
| `gerar_matriz_desafios.py` | Matriz desafio → código → regra → alerta → triagem. | exploratório |
| `gerar_candidatos_correcao.py` | Grupos exploratórios de correção a partir da matriz. | exploratório |
| `classificar_scan_combinado.py` | Classifica um scan novo por evidência histórica ou revisão explícita. | exploratório |
| `avaliar_codefixes.py` | Avalia no SAST as correções oficiais (codefixes) do Juice Shop. | exploratório |
| `recomparar_scans_arquivados.py` | Recompara evidências arquivadas com os comparadores v1 e v2. | exploratório |
| `revisar_associacoes.py` | Revisões explícitas das associações alerta ↔ desafio. | exploratório |
| `testar_rodada.py` | Entrada comum para conferir regras, relatório ou integração de uma rodada. | exploratório |
| `verificar_rodada8.py` … `verificar_rodada12.py` | Arquivam testes e hashes de cada rodada sem sobrescrever evidências. | exploratório |

`_bootstrap.py` e os `__init__.py` existem só para os imports funcionarem quando um script é executado
diretamente.
