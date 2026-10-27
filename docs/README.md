# Documentação

Na raiz de `docs/` ficam os documentos de **método** e de **ambiente**. Três deles são citados por
arquivos congelados do experimento e não podem mudar de lugar (marcados como **fixo**). Guias de uso,
planejamento, auditorias e histórico ficam em subpastas.

## Método e ambiente (raiz)

| Documento | Para que serve |
|---|---|
| [protocolo_experimental.md](protocolo_experimental.md) | Regras do experimento: alvo, SAST, filtragem, mapeamentos, critérios R/F/M e decisões de cada etapa. |
| [caderno_de_laboratorio.md](caderno_de_laboratorio.md) | Incidentes e decisões (Sintoma, Causa, Correção, Impacto). Fonte das Limitações do TCC. |
| [criterios_conjunto_d.md](criterios_conjunto_d.md) (fixo) | Critérios, escritos antes da classificação, para separar testes F e D. Citado por `config/conjunto_d.json`. |
| [conjunto_d.md](conjunto_d.md) (fixo) | Lista dos testes D, gerada por `scripts/experimento/gerar_conjunto_d.py`. |
| [cobertura_funcional.md](cobertura_funcional.md) | Revisão da cobertura funcional por caso (política `relacionada_v2`). |
| [validacao_relacionada.md](validacao_relacionada.md) | Por que só os testes da funcionalidade alterada são executados. |
| [aplicacao_ancoras.md](aplicacao_ancoras.md) | Aplicação de patches com recuo diferente (19/10). |
| [docker.md](docker.md) (fixo) | Ambiente único em Docker: imagem oficial, baseline, comandos. Citado pelo `Dockerfile`, `Makefile` e `compose.yaml`. |

## Guias de uso (`guias/`)

| Documento | Para que serve |
|---|---|
| [guias/painel_local.md](guias/painel_local.md) | Uso e limites do painel web. |
| [guias/modelo_colab.md](guias/modelo_colab.md) | Rodar o pipeline com o Qwen no Colab. |
| [guias/piloto_10_issues.md](guias/piloto_10_issues.md) | Os 10 casos do piloto e como consultar as respostas. |
| [guias/validacao_baseline_docker.md](guias/validacao_baseline_docker.md) | Como a referência Docker oficial foi gerada e validada (19/10). |
| [guias/referencia_detalhada.md](guias/referencia_detalhada.md) | O README anterior, completo: estratégias, métricas, validação em camadas e comandos de cada feature. |

## Planejamento (`planejamento/`)

| Documento | Para que serve |
|---|---|
| [planejamento/GUIA_CONTINUIDADE_TCC2.md](planejamento/GUIA_CONTINUIDADE_TCC2.md) | Diagnóstico e plano por entregas A–H. |

Documentos de planejamento que hoje existem só localmente (não versionados): `GUIA_ARRANQUE_TCC2.md`
(plano F0–F8), `ADENDO_01_comentarios_banca.md` (resposta aos comentários da banca, M1–M10),
`cronograma-acelerado.md` e `PROMPT_CLAUDE_CONTINUIDADE.md`. Ao versioná-los, o lugar deles é esta pasta.

## Auditoria das regras (`auditoria/`)

Relatórios da expansão exploratória das regras do Semgrep e de verificações pontuais.

| Documento | Assunto |
|---|---|
| [auditoria/auditoria_cobertura_semgrep.md](auditoria/auditoria_cobertura_semgrep.md) | Auditoria inicial da cobertura do Semgrep. |
| `auditoria/auditoria_rodada2.md` … `auditoria_rodada12.md` | Uma rodada de regras por arquivo. |
| [auditoria/avaliacao_referencias_codefixes.md](auditoria/avaliacao_referencias_codefixes.md) | Avaliação das correções oficiais (codefixes) do Juice Shop. |
| [auditoria/comparador_v2.md](auditoria/comparador_v2.md) | Entrega e calibração do comparador v2. |
| [auditoria/correcao_validacao_piloto10.md](auditoria/correcao_validacao_piloto10.md) | Correção da validação do piloto de 10 casos. |
| [auditoria/selecao_exploratoria_correcao.md](auditoria/selecao_exploratoria_correcao.md) | Seleção para uma eventual segunda rodada de correções. |

## Histórico (`historico/`)

| Documento | Para que serve |
|---|---|
| [historico/README.md](historico/README.md) | O que mudou de lugar em 26/10/2026 (caminho antigo → novo). |
| [historico/features/](historico/features/README.md) | Pedidos (README) e relatórios de entrega (ENTREGA) das features 01–07. |
| [historico/estrutura_projeto.md](historico/estrutura_projeto.md) | Descrição anterior da estrutura, substituída por estes índices. |

## Outros mapas

- Estrutura do repositório: [README.md](../README.md)
- Arquitetura do código, por etapa: [src/pipeline/README.md](../src/pipeline/README.md)
- Comandos avulsos: [scripts/README.md](../scripts/README.md)
- Configuração e entradas: [config/README.md](../config/README.md)
- Resultados: [outputs/README.md](../outputs/README.md)
