# Configuração e entradas do experimento (`config/`)

Esta pasta mistura três tipos de arquivo. Eles continuam juntos porque o código, o baseline oficial, a
referência Docker e os resultados arquivados apontam para estes caminhos. **Não mova, não renomeie e não
edite** os arquivos marcados como congelados: isso muda a identidade científica do experimento e faz o
preflight recusar o baseline oficial.

## 1. Entradas congeladas do experimento

| Arquivo | Para que serve | Quem confere |
|---|---|---|
| `perfis/ampliado_piloto_v1/` | Perfil SAST usado pela campanha: regras locais e do registro exportado, escopo, flags e timeouts. | contrato da execução (`perfil_sha256`) |
| `perfis/ampliado_v1/` | Perfil anterior, com as mesmas regras e outro `perfil.json`. **Não carrega com o código atual** ("Hash de regra inválido"); nenhum config o usa. Mantido como evidência. | — |
| `cobertura_funcional_v1.yaml` | Revisão, caso a caso, de quais testes cobrem cada alerta. Define os 52 casos preparados e os 26 bloqueados. | baseline oficial, referência Docker |
| `mapa_testes_relacionados_v2.yaml` | Arquivo alterado → grupos de testes da política `relacionada_v2`. | baseline oficial, referência Docker |
| `conjunto_d_cobertura_v1.json` | Testes D (dependem da vulnerabilidade) usados na cobertura funcional. | baseline oficial, referência Docker |
| `conjunto_d.json` | Lista de testes D usada pelo runner. Caminho fixo em `src/pipeline/etapas/e07_validacao/conjunto_d.py`. | contrato da execução |
| `prompts/roteiro_raciocinio_guiado.md` | Roteiro em etapas usado por P2 e P4. | contrato da execução |
| `mapa_cwe_vuln.yaml` | CWE → sigla da vulnerabilidade (SQLI, XSS, ...). | catálogo |
| `mapa_owasp.yaml` | OWASP 2021 → OWASP 2025. | catálogo |
| `mapa_categoria_rag.yaml` | Sigla → categoria do RAG. | catálogo |
| `semgrepignore` | Exclusões do escopo do SAST. Incorporadas ao escopo do perfil por `congelar_perfil_sast.py`; lidas diretamente pelo modo histórico. | perfil |
| `precos_llm.yaml` | Preço por token, para o custo registrado. | `llm/openai_client.py` |
| `modelos/manifesto_colab.json` | Identidade do modelo Qwen servido no Colab. | cliente Colab, via `COLAB_MODEL_MANIFEST` no `.env` |

## 2. Configurações de execução (lidas por `executar.py`, `make` e pelo painel)

| Arquivo | O que roda |
|---|---|
| `execucao_docker_preparados.yaml` | Os 52 casos preparados, P1–P4, baseline oficial do Docker. **Padrão do `Makefile`.** |
| `execucao_docker_78.yaml` | Os 78 casos. O preflight recusa enquanto houver lacunas de cobertura. |
| `execucao.yaml` | Piloto de 10 casos com o baseline anterior ao Docker. Padrão do `executar.py` e do `painel.py` fora do `make`. |
| `execucao_colab_1_issue.yaml` | Teste do Qwen no Colab com 1 caso. |
| `execucao_cobertura.exemplo.yaml`, `execucao_otimizada.exemplo.yaml` | Exemplos das políticas `relacionada_v2` e `otimizada_v1`. |

Para outra combinação, copie um destes arquivos e passe `CONFIG=<arquivo>` ao `make` ou `--config <arquivo>`
ao `executar.py`.

## 3. Auditoria exploratória das regras do Semgrep

Usados pelos scripts de `scripts/auditoria/` e `scripts/relatorios/relatorio_rodadaN.py`; não entram na campanha.

| Arquivo | Conteúdo |
|---|---|
| `auditoria_desafios.yaml` | Anotações da matriz desafio ↔ alerta. |
| `auditoria_desafios_rodada2.yaml` … `auditoria_desafios_rodada12.yaml` | Anotações de cada rodada de regras. |
| `revisoes_associacoes_v1.yaml` | Revisões explícitas das associações alerta ↔ desafio (padrão de `recomparar_scans_arquivados.py`). |
| `revisoes_associacoes_rodada6.yaml` | Revisões da rodada 6. |
| `candidatos_correcao_exploratorios.yaml` | Candidatos de correção para uma eventual segunda rodada. |
| `semgrep-rules-referencia/` | 7 regras do registro do Semgrep guardadas como referência. |

## 4. Legado e sem uso

| Arquivo | Situação |
|---|---|
| `mapa_testes_relacionados.yaml` | Versão 1 do mapa de testes; usada só pela política `otimizada_v1`. |
| `config.yaml` | Vazio. Mantido porque aparece em registros antigos de `outputs/`. |
