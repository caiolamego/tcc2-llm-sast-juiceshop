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
| `conjunto_d_cobertura_v2.json`, `cobertura_funcional_v7.yaml`, `mapa_testes_relacionados_v8.yaml` | Versão vigente: acrescenta ao conjunto D o critério (d), com testes ligados a casos. Gerados por `scripts/experimento/gerar_conjunto_d_por_caso.py`. | contrato da execução |
| `conjunto_d.json` | Lista de testes D usada pelo runner. Caminho fixo em `src/pipeline/etapas/e07_validacao/conjunto_d.py`. | contrato da execução |
| `prompts/roteiro_raciocinio_guiado.md` | Roteiro em etapas usado por P2 e P4. | contrato da execução |
| `mapa_cwe_vuln.yaml` | CWE → sigla da vulnerabilidade (SQLI, XSS, ...). | catálogo |
| `mapa_owasp.yaml` | OWASP 2021 → OWASP 2025. | catálogo |
| `mapa_categoria_rag.yaml` | Sigla → categoria do RAG. | catálogo |
| `semgrepignore` | Exclusões do escopo do SAST. Incorporadas ao escopo do perfil por `congelar_perfil_sast.py` (o modo histórico, que também as lia, saiu do código em 01/11/2026). | perfil |
| `precos_llm.yaml` | Preços Standard dos três modelos OpenAI, leitura/escrita de cache do provedor e custo registrado. A tabela e seu hash entram nas novas identidades de inferência. | `src/pipeline/etapas/e05_geracao_llm/cliente_openai.py` |
| `modelos/manifesto_colab.json` | Identidade do modelo Qwen servido no Colab. | cliente Colab, via `COLAB_MODEL_MANIFEST` no `.env` |

## 2. Configurações de execução (lidas por `executar.py`, `make` e pelo painel)

O campo opcional `modelo` aceita `gpt-4.1-mini`, `gpt-5.6-luna` ou `gpt-6-luna`.
Ele seleciona OpenAI mesmo que o `.env` ainda aponte para Colab. A opção `--modelo`
no terminal ou a seleção no painel prevalece sobre o YAML; o YAML prevalece sobre
`OPENAI_MODEL`. Sem seleção explícita, o provedor/configuração anterior continua
disponível. A configuração dos 78 casos define `modelo: gpt-4.1-mini` como padrão.

Os perfis de geração são definidos no código: 4.096 tokens máximos, temperatura zero,
seed configurada somente no GPT-4.1 mini e `reasoning_effort=none` nos Luna.
O limite de chamadas e o orçamento monetário continuam acumulados entre modelos;
selecionar outro modelo não reinicia nem aumenta os limites do `.env`.

| Arquivo | O que roda |
|---|---|
| `execucao_docker_preparados.yaml` | Os 52 casos preparados, P1–P4, baseline da referência Docker. Use com `CONFIG=` ou `--config`. |
| `execucao_docker_78.yaml` | **Padrão do `executar.py`, do `painel.py` e do `Makefile`.** Os 78 casos, revisão funcional v7, mapa v8 e baseline gerado em 05/11/2026 na imagem `81fe`. Como `docker/referencia.json` não acompanha a v7, use `docker compose run` em vez dos atalhos `make docker-*`. Preserva modo real/K=4; use `--modo preflight` para conferir sem geração. Imagem e comandos em `docs/cobertura_funcional_v6.md`. |
| `execucao_piloto_3_casos.yaml` | Teste de ponta a ponta com 3 casos, P1–P4, K=3. Vem em `dry-run`; para chamar a LLM, use `--modo real`. |
| `execucao.yaml` | Piloto de 10 casos com o baseline anterior ao Docker. Use com `--config`. |
| `execucao_colab_1_issue.yaml` | Teste do Qwen no Colab com 1 caso. |
| `execucao_cobertura.exemplo.yaml`, `execucao_otimizada.exemplo.yaml` | Exemplos das políticas `relacionada_v2` e `otimizada_v1`. |

Para outra combinação, copie um destes arquivos e passe `CONFIG=<arquivo>` ao `make` ou `--config <arquivo>`
ao `executar.py`.

### Ampliação funcional iniciada em 02/11/2026

`cobertura_funcional_v2.yaml` e `mapa_testes_relacionados_v3.yaml` acrescentam avaliações independentes
de aritmética/persistência de CAPTCHA, extração ZIP e descontos de campanha. Os controles de regressão
estão em `controles_cobertura_v2.json`. A versão anterior continua congelada e ligada à campanha de 19/10.
`execucao_cobertura_v2_preflight.yaml` seleciona os casos com revisão suficiente e usa o baseline novo,
em modo preflight, sem chamadas à LLM.
As evidências desta ampliação ficam em `outputs/cobertura_funcional/AMPLIACAO_20261102/`.
Consulte [cobertura funcional v2](../docs/cobertura_funcional_v2.md) para o estado verificado, comandos e
lacunas restantes. A referência Docker oficial e os padrões de execução não são trocados por essa revisão.

O segundo incremento usa `cobertura_funcional_v3.yaml`, `mapa_testes_relacionados_v4.yaml` e
`controles_cobertura_v3.json` para o bloco de `server.ts`. Sua configuração optativa é
`execucao_cobertura_v3_preflight.yaml`; veja [a revisão e as evidências](../docs/cobertura_funcional_v3.md).

O terceiro incremento usa `cobertura_funcional_v4.yaml`, `mapa_testes_relacionados_v5.yaml`,
`controles_cobertura_v4.json` e `execucao_cobertura_v4_preflight.yaml` para os dois casos de
`lib/codingChallenges.ts`. Veja [contratos e evidências](../docs/cobertura_funcional_v4.md).

O quarto incremento usa `cobertura_funcional_v5.yaml`, `mapa_testes_relacionados_v6.yaml`,
`controles_cobertura_v5.json` e `execucao_cobertura_v5_preflight.yaml` para o seed TOTP.
Veja [os contratos e o controle positivo de rotação](../docs/cobertura_funcional_v5.md).

O fechamento dos seis casos restantes usa `cobertura_funcional_v6.yaml`, `mapa_testes_relacionados_v7.yaml`,
`controles_cobertura_v6.json` e `execucao_cobertura_v6_preflight.yaml`, com todos os 78 casos.
Veja [independência dos avaliadores e limitações](../docs/cobertura_funcional_v6.md).

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
