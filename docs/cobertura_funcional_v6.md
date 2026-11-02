# Fechamento da cobertura do catálogo de 78 casos

Incremento de 02/11/2026 para os seis casos que restavam após a revisão v5. Acrescenta cinco grupos,
com 27 testes externos ao alvo, preservando os grupos e resultados anteriores. Não executa campanha
de correção com LLM nem altera o conjunto D.

## Resultado verificado

- **78 casos preparados e zero bloqueados**, nas mesmas 78 ocorrências e 46 arquivos do catálogo.
- Auditoria: `campanha_78_preparada=true`; seis casos liberados desde a revisão v5, sem perder os 72
  já preparados.
- Baseline completo: **51 grupos comparáveis, 571 testes aprovados e seis ignorados**, com compilações
  de servidor e frontend aprovadas. Ignorados não contam como executados. As subavaliações metamórficas
  têm relatórios próprios e não são somadas como novas tentativas do experimento.
- Os **46 grupos anteriores** mantêm identidades, estados e testes obrigatórios aprovados, no mesmo
  ambiente registrado; os cinco novos grupos completam a revisão. Comparação em `comparacao_com_v5.json`.
- **14/14 controles negativos detectados**; cinco alterações funcionais válidas aceitas, com os
  originais restaurados. Os 365 testes unitários do projeto passaram.
- Preflight `AMP_PREFLIGHT_20261102T234303Z_5c109744` concluído com **78 casos e K=4**, zero tentativas
  de correção e nenhuma chamada à API. Executado pela configuração completa, com `--modo preflight`.

Resumo, seis IDs liberados e hashes das entradas/evidências:
`outputs/cobertura_funcional/FINAIS_20261102/resumo_fechamento_78.json`.

O código 2 do comparador de baselines indica os grupos adicionais e a identidade de cobertura ampliada,
sem diferenças funcionais nos grupos compartilhados. Evidências principais: `baseline/baseline_testes.json`,
`auditoria/resumo.json`, `controles/controles.json`, `alteracoes_validas/controles_positivos.json` e
`consulta_estruturada/resultado.json` na pasta deste incremento. O plano de lacunas publicado pela
auditoria não contém casos bloqueados.

## Contratos e independência

| Grupo | Avaliação |
|---|---|
| `chat_reviews` | Express, SDK e banco reais, com respostas SSE simuladas no transporte do modelo. Verifica avaliações exatas por produto, exclusão de avaliações alheias, vazio, ID numérico, definições de ferramenta, demais ferramentas e fim/erro do stream. |
| `video_parser` | Compila o template Pug real e executa seu JavaScript com interfaces controladas de documento/VTTCue. Confere tempos, texto, criação da trilha e erros. O grupo API `video` existente também acompanha esse caso. |
| `grunt_artifacts` | Executa as tarefas reais de pacote em diretório temporário, com plugins instalados. Abre o tar, confere arquivos/bytes, exclusões, manifesto e checksums. Aceita digest MD5 legado ou SHA-256/384/512 com extensão coerente. |
| `frontend_contracts` | Angular/jsdom real: guards e componente LastLoginIp com JWTs gerados, papéis distintos, ausência de token e renderização normal/sem IP. |
| `frontend_spec_integrity` | Avaliador externo executa os specs candidatos, exige o inventário original sem skips e repete as suítes com métodos de produção temporariamente quebrados. O cenário específico deve detectar sua regressão. |

Os três casos em `.spec.ts` usam os dois grupos independentes de frontend. O spec candidato pode mudar;
não é aprovado por seu próprio resultado isolado nem bloqueado pelo hash original da fixture. O
avaliador protegido confere que todos os cenários continuam presentes e detectam decoder quebrado,
IP omitido e IP fabricado. Os métodos temporariamente alterados são restaurados byte a byte, inclusive
quando uma verificação falha. A seleção inclui frontend e API, preservando a conferência das
dependências Angular e a compilação dos domínios; não foi necessário alterar os adaptadores do pipeline.

Relatórios JUnit, logs e hashes das execuções Angular internas são preservados em `subavaliacoes/`
nas evidências, com o hash do spec candidato. Falhas de mutantes nessas subavaliações são esperadas,
não falhas do baseline nem tentativas independentes de remediação.

## Controles

Os 14 controles negativos verificam perda/contaminação de avaliações do chat, erro de stream omitido,
parser/trilha/tempo incorretos, checksum incorreto/ausente, arquivo indevido no pacote e três formas de
remover asserções dos specs. Cada controle exige falha nominal do teste externo esperado, sem falha
operacional.

Os controles positivos verificam cinco refatorações funcionais:

1. JWT do guard gerado a partir do payload, sem preservar o literal original.
2. JWTs do componente gerados em tempo de execução.
3. Substituição conjunta de MD5 por SHA-256 e extensão `.sha256`.
4. Separação literal `-->` com trim em lugar da regex do parser.
5. Consulta estruturada `{ product: productId }` em lugar de `$where`, preservando a seleção de avaliações.

Esses controles demonstram aceitação de alterações válidas e restauração do alvo. Não são correções
produzidas por LLM nem entram nas métricas de remediação. O código da prova fica em
`outputs/cobertura_funcional/FINAIS_20261102/ferramentas/provar_alteracoes_validas.py`.
A prova da consulta estruturada está em `ferramentas/provar_consulta_estruturada.py`, com resultados
em `consulta_estruturada/` no mesmo incremento.

## Limitações observadas

A validação inicial encontrou no parser original um cue sem texto para entrada CRLF. Esta revisão
exercita VTT/SRT em LF e não comprova compatibilidade CRLF ou cues iniciados em zero. O alvo não foi
alterado para fazer o baseline passar. A evidência inicial foi preservada. Também houve ajustes do
avaliador para comparar arrays entre contextos e enumerar somente declarações de testes; o teste de
cupom usa desconto 10, suportado pelo encoder atual.

As interfaces nativas de vídeo são controladas; não se demonstra reprodução audiovisual num navegador.
O pacote usa arquivos de fixture, sem redistribuir todo o node_modules. Os testes de frontend avaliam
integridade dos cenários declarados e mutantes conhecidos, não prova formal de correção dos testes.
Prontidão funcional não demonstra ausência de vulnerabilidades nem transforma falsos positivos em
falhas confirmadas. Os 78 casos mantêm as classificações originais de auditoria.

## Entradas e reprodução

- Revisão: `config/cobertura_funcional_v6.yaml`.
- Mapa: `config/mapa_testes_relacionados_v7.yaml`, schema `2.0` e política `relacionada_v2` preservados.
- Controles: `config/controles_cobertura_v6.json`.
- Preflight optativo: `config/execucao_cobertura_v6_preflight.yaml`, K=1 e nenhuma chamada de geração.
- Configuração completa existente: `config/execucao_docker_78.yaml`, atualizada para esta revisão,
  preservando o modo real e K=4. Use `--modo preflight` para conferir sem geração.
- Evidências: `outputs/cobertura_funcional/FINAIS_20261102/`.
- Imagem: `sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5`.

Use o ID da imagem em `TCC_DOCKER_IMAGE`. Os comandos de controles, baseline e auditoria dos
[incrementos anteriores](cobertura_funcional_v4.md#reprodução-sem-llm) aceitam as entradas acima;
use destinos inéditos e execute sequencialmente com o checkout preparado e limpo.

```bash
docker compose run --rm --no-deps tcc .venv/bin/python executar.py \
  --config config/execucao_cobertura_v6_preflight.yaml
```

O script de controles positivos recusa saída existente; para outra rodada, preserve o original e use
uma cópia em outra pasta de incremento, ajustando os caminhos. Não execute verificações simultâneas
na mesma worktree. Todos os originais e resultados anteriores permanecem preservados.

Para verificar também a configuração completa com quatro worktrees:

```bash
docker compose run --rm --no-deps tcc .venv/bin/python executar.py \
  --config config/execucao_docker_78.yaml --modo preflight
```

O padrão de 52 casos do Makefile e a referência Docker histórica permanecem identificados separadamente;
os comandos desta revisão usam a imagem registrada acima. Nenhuma execução em modo real foi iniciada.
