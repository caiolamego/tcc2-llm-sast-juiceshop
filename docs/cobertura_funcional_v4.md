# Terceiro incremento — desafios de código

Revisão de 02/11/2026 para as duas ocorrências de `lib/codingChallenges.ts`. O grupo
`coding_challenges` acrescenta 11 testes em `tests/functional/juice_shop/coding_challenges.unit.test.ts`.
As revisões, baselines, configurações e resultados anteriores permanecem preservados.

## Resultado verificado

- **71 casos preparados e sete bloqueados**, das mesmas 78 ocorrências; antes eram 69/9.
- As duas ocorrências de `lib/codingChallenges.ts` foram liberadas, sem perder casos antes preparados.
- Baseline: **45 grupos comparáveis, 535 testes aprovados e seis ignorados**, com compilações de
  servidor e frontend aprovadas. Ignorados não contam como executados.
- Os **44 grupos anteriores** mantêm identidades, estados e testes obrigatórios aprovados; ambiente
  registrado igual ao do incremento anterior. O grupo adicional é `coding_challenges`.
- **8/8 controles detectados** e arquivos restaurados; 32 testes unitários da cobertura/executor aprovados.
- Preflight `AMP_PREFLIGHT_20261102T223253Z_759c2764` concluído para **71 casos**, sem tentativas de
  correção ou chamadas à API.

Resumo com os dois IDs liberados e hashes:
`outputs/cobertura_funcional/CODING_CHALLENGES_20261102/resumo_bloco_coding_challenges.json`.

A comparação está em `comparacao_com_v3.json` nas evidências. O código 2 do comparador indica o grupo
adicional e a identidade de cobertura ampliada, sem diferença funcional nos grupos compartilhados.
As sete lacunas restantes estão no plano publicado em `auditoria/plano_testes_adicionais.md`:
chat, seed TOTP, dois casos nos testes de last-login-ip, teste de app.guard, template de legendas e Grunt.

## Contratos observados

O avaliador transpila o módulo real completo, com TypeScript instalado no alvo, e executa suas funções
públicas em um contexto isolado. Somente filesystem e logger são controlados. Não copia a implementação
da extração nem substitui os resultados das expressões regulares.

Os testes conferem:

- Trecho visível e índices vulneráveis/neutros de dois desafios distintos no mesmo arquivo.
- Remoção de marcadores, linhas e blocos ocultos antes da numeração das linhas.
- Preservação de conteúdo e índices em LF, CRLF e CR; comentários `#` em arquivos de dados.
- Descoberta recursiva, descarte de arquivos sem limites de desafio e continuidade/log de erro de leitura.
- Erro `BrokenBoundary` com a chave do desafio quando falta o limite final.
- Mapa vazio sem desafios e reutilização do cache sem reler arquivos alterados.

Os oito controles temporários alteram os índices de linhas vulneráveis/neutras, removem a seleção por
chave em cada tipo de marcador, omitem remoção de linha oculta, ignoram limite inválido, invalidam o cache
ou omitem a recursão. Exigem falha do teste nominal esperado e restauração dos bytes originais.

A validação inicial revelou uma diferença de protótipos entre arrays do contexto isolado e do avaliador:
a lista de arquivos tinha o conteúdo correto, mas a comparação estrita reprovava os protótipos. O teste
foi ajustado para comparar arrays locais, como já fazia com os índices. Essa rodada está preservada em
`validacao_inicial/`; não é um defeito atribuído ao alvo nem o baseline final da revisão.

## Identidade e limites

- Revisão: `config/cobertura_funcional_v4.yaml`.
- Mapa: `config/mapa_testes_relacionados_v5.yaml`, schema `2.0` e política `relacionada_v2` preservados.
- Controles: `config/controles_cobertura_v4.json`.
- Configuração optativa: `config/execucao_cobertura_v4_preflight.yaml`, modo preflight e K=1.
- Evidências: `outputs/cobertura_funcional/CODING_CHALLENGES_20261102/`.
- Imagem: `sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5`.

Os testes são F; o conjunto D não foi alterado. Arquivos virtuais permitem verificar contratos com
entradas conhecidas e falhas de leitura controladas; não comprovam I/O físico, desempenho ou segurança
da regex para chaves fora do contrato observado. Nenhuma vulnerabilidade é considerada corrigida por
esses testes, e não há geração LLM nesta ampliação.

## Reprodução sem LLM

Na raiz do projeto, use o ID da imagem acima em `TCC_DOCKER_IMAGE` e destinos inéditos. Execute os
comandos sequencialmente, com a worktree preparada e limpa:

```bash
docker compose run --rm --no-deps tcc .venv/bin/python \
  scripts/experimento/validar_controles_cobertura.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 --revisao config/cobertura_funcional_v4.yaml \
  --mapa-testes config/mapa_testes_relacionados_v5.yaml \
  --controles config/controles_cobertura_v4.json \
  --saida outputs/cobertura_funcional/NOVA_RODADA_CODING/controles
```

```bash
docker compose run --rm --no-deps tcc .venv/bin/python \
  scripts/experimento/gerar_baseline_funcional.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 --revisao config/cobertura_funcional_v4.yaml \
  --mapa-testes config/mapa_testes_relacionados_v5.yaml \
  --saida outputs/cobertura_funcional/NOVA_RODADA_CODING/baseline
```

Para auditar, use `scripts/auditoria/auditar_cobertura_funcional.py` com os mesmos catálogo, checkout,
revisão e mapa, acrescentando `--baseline-testes` com o JSON do novo baseline e `--saida` com uma pasta
inédita. Não use o baseline de outra revisão.

O preflight optativo aponta ao baseline publicado neste incremento:

```bash
docker compose run --rm --no-deps tcc .venv/bin/python executar.py \
  --config config/execucao_cobertura_v4_preflight.yaml
```

Em outra pasta de evidências, ajuste o caminho do baseline numa cópia da configuração. O preflight
verifica preparação; não executa testes funcionais nem chama a LLM.
