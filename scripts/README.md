# Comandos avulsos (`scripts/`)

Comandos executados à mão, fora do fluxo automático do `executar.py`. Rode-os a partir da raiz do
repositório, de preferência dentro do container (`docker compose run --rm tcc python scripts/...`). Todos
aceitam `--help`.

Situação: **núcleo** (usado na campanha atual), **apoio** (diagnóstico e verificação), **legado** (modo
histórico E01–E03 ou preparação anterior ao Docker), **exploratório** (auditoria das regras do Semgrep).

Os nomes atuais valem desde 26/10/2026. Registros antigos em `outputs/` e relatórios de auditoria citam os
nomes anteriores (`scripts/experiment/...`, `scripts/audit/...`); a correspondência está em
`docs/historico/README.md`.

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
| `gerar_conjunto_d.py` | Gera `config/conjunto_d.json` e `docs/conjunto_d.md` a partir dos critérios. | núcleo |
| `replay_patches.py` | Replay de patches arquivados com SAST e testes reais, sem LLM (`--revalidacao`). | apoio |
| `replay_ancoras.py` | Reaplica respostas com âncora ausente em cópias temporárias. | apoio |
| `diagnosticar_llm.py` | Diagnóstico da LLM: offline, conexão, mensagem curta ou prompt arquivado. | apoio |
| `validar_base_rag.py` | Valida a base RAG ou publica um manifesto novo. | apoio |
| `gerar_catalogo_historico.py` | Catálogo histórico de 12 casos (JS001–JS012). | legado |
| `gerar_linha_de_base_historica.py` | Linha de base de testes do modo histórico. | legado |
| `marcar_desafios_historicos.py` | Cruza o catálogo histórico com os marcadores de desafio. | legado |
| `tentar_um_caso.py` | Uma tentativa ponta a ponta sobre um caso (fase F5). | legado |
| `sondagem_sast.py` | Sondagem do oráculo R, sem LLM (fase F5). | legado |
| `validar_cenarios_camadas.py` | Confere a validação em camadas em 3 cenários (fase F4.3). | legado |
| `medir_custo_validacao.py` | Mede o custo de cada camada de validação, incluindo o único uso do Cypress (fase F2.4). | legado |

## `relatorios/` — relatórios e métricas

| Script | Para que serve | Situação |
|---|---|---|
| `consolidar_metricas.py` | Consolida as métricas de uma execução em JSON e CSV (chamado pelo `executar.py`). | núcleo |
| `relatorio_revalidacao.py` | Compara uma revalidação sem LLM com os registros originais. | apoio |
| `relatorio_replays.py` | Compara replays concluídos. | apoio |
| `metricas_historicas.py` | Métricas do modo histórico (E01, E02) nas três definições de F. | legado |
| `relatorio_baseline_historico.py` | Relatório do baseline SAST histórico. | legado |
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
