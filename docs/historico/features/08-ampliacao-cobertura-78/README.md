# Feature 08 — Ampliação da cobertura funcional para os 78 casos

**Status:** implementada e validada; 78 casos preparados e nenhum bloqueado. Campanha real com LLM pendente.  
**Data:** 02/11/2026.  
**Continuação:** [feature 06 — cobertura funcional](../06-cobertura-funcional/README.md).

## Objetivo e resultado

Ampliar os testes funcionais usados para avaliar a preservação de comportamento após
um patch produzido por LLM. A entrega histórica da feature 06 havia preparado 52 das
78 ocorrências do catálogo SAST. As outras 26 tinham lacunas de avaliação que impediam
sua participação na campanha completa.

Foram acrescentados testes independentes, controles de regressão, revisões de cobertura
e mapas de seleção versionados. A auditoria final confirmou **78 ocorrências preparadas,
em 46 arquivos**, sem remover casos do catálogo ou alterar suas classificações.

“Preparado” significa que o caso possui revisão adequada, seleção executável e baseline
comparável, com compilação dos domínios aplicáveis. O patch futuro ainda precisa passar
pela avaliação funcional e pela avaliação SAST. Esta entrega não representa 78 correções
nem confirma 78 vulnerabilidades.

## O que foi acrescentado

| Incremento | Comportamentos avaliados | Casos preparados após o incremento | Documentação |
|---|---|---|---|
| Revisão v2 | CAPTCHA aritmético, extração de ZIP e descontos de campanha | 57/78 | [Detalhes e evidências](../../../cobertura_funcional_v2.md) |
| Revisão v3 | Recursos REST gerados em `server.ts` e medição de inicialização, incluindo propagação e log de erros | 69/78 | [Detalhes e evidências](../../../cobertura_funcional_v3.md) |
| Revisão v4 | Extração dos desafios de código, marcadores, índices, recursão, cache e erros de leitura | 71/78 | [Detalhes e evidências](../../../cobertura_funcional_v4.md) |
| Revisão v5 | Seed de usuários, persistência do segredo TOTP e fluxo de autenticação com segundo fator | 72/78 | [Detalhes e evidências](../../../cobertura_funcional_v5.md) |
| Revisão v6 | Chat, legendas, empacotamento/checksums e integridade dos testes Angular | 78/78 | [Detalhes e evidências](../../../cobertura_funcional_v6.md) |

Os testes adicionais ficam em [tests/functional/juice_shop](../../../../tests/functional/juice_shop/).
O runner os materializa temporariamente no ambiente de avaliação. Eles não são incorporados
ao código congelado do Juice Shop nem enviados aos prompts/RAG como soluções.

### Fechamento dos seis casos restantes

A revisão v6 acrescentou cinco grupos, com 27 testes:

| Grupo | O que verifica |
|---|---|
| `chat_reviews` | Seleção exata de avaliações por produto, ausência de avaliações alheias, resultados vazios, ferramentas do chat e término/erro do stream. Usa Express, SDK e banco reais, com transporte do modelo simulado. |
| `video_parser` | JavaScript extraído do template Pug real: criação da trilha, texto, tempos e erros na leitura de legendas. Complementa o grupo API de vídeo existente. |
| `grunt_artifacts` | Tarefas Grunt reais em diretório temporário: conteúdo do pacote, exclusões, manifesto e digest coerente com a extensão do checksum. |
| `frontend_contracts` | Guards, papéis de usuário e renderização do componente LastLoginIp usando Angular/jsdom e JWTs gerados durante os testes. |
| `frontend_spec_integrity` | Presença dos cenários originais nos specs candidatos e capacidade de detectar regressões deliberadas nos métodos de produção. |

Três ocorrências estão em arquivos `.spec.ts`. Nesses casos, aprovar apenas o teste
alterado permitiria que um patch passasse ao remover suas próprias asserções. O avaliador
externo exige os cenários originais sem skips e repete os testes com decoder quebrado,
IP omitido ou IP fabricado. O cenário correspondente deve detectar a regressão.
Os arquivos de produção são restaurados byte a byte após essas verificações.

## Como foi validado

O baseline final executou os 51 grupos da revisão, com compilações de servidor e frontend
aprovadas. Os 46 grupos da revisão anterior mantiveram os mesmos resultados no ambiente
registrado. Não foi necessário alterar os adaptadores do pipeline no fechamento v6.

| Verificação final | Resultado |
|---|---|
| Auditoria de preparação | 78 preparados, zero bloqueados; `campanha_78_preparada=true` |
| Baseline funcional completo | 571 testes aprovados e seis ignorados, em 51 grupos comparáveis |
| Testes unitários do projeto | 365 aprovados |
| Controles negativos da revisão v6 | 14/14 regressões detectadas, com restauração dos originais |
| Controles positivos da revisão v6 | Cinco alterações funcionais válidas aceitas |
| Preflight da configuração completa | 78 casos, K=4, zero tentativas de correção e nenhuma chamada à API |

Os controles negativos exigem falha do teste nominal esperado, sem confundir erro
operacional com regressão detectada. Os positivos verificam que a avaliação aceita
refatorações válidas: JWTs gerados, migração de MD5 para SHA-256, separação literal de
timestamps e consulta estruturada de avaliações no lugar de `$where`.

Os seis testes ignorados não contam como executados. As falhas esperadas dos mutantes
Angular têm relatórios próprios; não são falhas do baseline nem tentativas de remediação.
Os controles de cada incremento anterior estão documentados nos respectivos relatórios.

## Configurações e evidências

- [Revisão de cobertura v6](../../../../config/cobertura_funcional_v6.yaml).
- [Mapa de testes v7](../../../../config/mapa_testes_relacionados_v7.yaml), schema `2.0`.
- [Controles negativos v6](../../../../config/controles_cobertura_v6.json).
- [Configuração de preflight v6](../../../../config/execucao_cobertura_v6_preflight.yaml), K=1.
- [Configuração completa dos 78 casos](../../../../config/execucao_docker_78.yaml), atualizada para a revisão v6 e seu baseline; preserva modo real e K=4.
- [Resumo do fechamento com IDs e hashes](../../../../outputs/cobertura_funcional/FINAIS_20261102/resumo_fechamento_78.json).
- [Baseline completo](../../../../outputs/cobertura_funcional/FINAIS_20261102/baseline/baseline_testes.json).
- [Auditoria final](../../../../outputs/cobertura_funcional/FINAIS_20261102/auditoria/resumo.json).
- [Controles negativos](../../../../outputs/cobertura_funcional/FINAIS_20261102/controles/controles.json), [quatro controles positivos](../../../../outputs/cobertura_funcional/FINAIS_20261102/alteracoes_validas/controles_positivos.json) e [consulta estruturada](../../../../outputs/cobertura_funcional/FINAIS_20261102/consulta_estruturada/resultado.json).
- [Preflight completo validado](../../../../outputs/campanha_docker/AMP_PREFLIGHT_20261102T234303Z_5c109744/preflight.json).

As revisões anteriores, mapas, baselines e resultados históricos foram preservados.
O catálogo, o conjunto D e os denominadores científicos não foram alterados.
O padrão de 52 casos do Makefile e a referência Docker histórica permanecem separados
da configuração explícita dos 78 casos.

## Conferência sem chamadas à LLM

Na raiz do projeto, com Docker, volumes, dependências e worktrees preparados, selecione
a imagem usada na validação:

```bash
export TCC_DOCKER_IMAGE=sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5
```

Para conferir a preparação da configuração completa com quatro worktrees:

```bash
docker compose run --rm --no-deps tcc .venv/bin/python executar.py \
  --config config/execucao_docker_78.yaml --modo preflight
```

O parâmetro `--modo preflight` é necessário nesse comando porque o YAML completo
preserva `modo: real`. Preflight verifica preparação e identidade dos artefatos;
não executa os testes funcionais nem chama a LLM. As execuções reais dos testes
estão registradas no baseline.

Para gerar novas evidências de testes, siga a [reprodução da revisão v6](../../../cobertura_funcional_v6.md#entradas-e-reprodução),
usando destinos inéditos e executando controles, baseline e auditoria sequencialmente.
Não reutilize baseline de outra revisão nem execute verificações simultâneas na mesma worktree.

## Limitações e trabalho pendente

O parser original de legendas produziu um cue sem texto para entrada CRLF na validação
inicial. Os testes finais cobrem VTT/SRT com LF e não comprovam suporte a CRLF ou cues
iniciados em zero. O alvo não foi alterado para fazer o baseline passar; a evidência
inicial permanece arquivada.

Os testes de vídeo usam interfaces controladas, sem demonstrar reprodução audiovisual
em navegador. Os testes do pacote usam fixtures. A avaliação de integridade dos specs
cobre cenários e mutantes conhecidos, sem constituir prova formal da correção dos testes.

A campanha real com LLM continua pendente. Esta entrega conclui a preparação funcional
do catálogo; resultados de correção e eficácia dos prompts dependem dessa campanha.
