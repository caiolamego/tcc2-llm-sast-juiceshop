# Ampliação da cobertura funcional — 02/11/2026

Primeiro incremento para avaliar todos os 78 casos do catálogo SAST. A revisão v2 acrescenta três grupos
independentes, com 16 testes funcionais, para as lacunas de cinco casos: dois em `routes/captcha.ts`, um
em `routes/fileUpload.ts` e dois em `routes/order.ts`.

Os artefatos da revisão v1, a referência Docker e a campanha de 19/10/2026 permanecem preservados.
Esta revisão possui identidade própria e ainda deixa outros casos bloqueados. Não é uma campanha de
correções nem demonstra eficácia de uma LLM.

## Resultado verificado

- Auditoria: **57 preparados, 21 bloqueados**, entre as mesmas 78 ocorrências (antes: 52/26).
- Baseline completo: **42 grupos comparáveis, 500 testes aprovados e seis ignorados**, compilações de
  servidor e frontend aprovadas. Os ignorados são identificados e não contam como executados.
- Os **39 grupos anteriores** mantêm as mesmas identidades de teste, estados e obrigatórios aprovados;
  os outros três grupos são os novos. A comparação está em `comparacao_com_v1.json` nas evidências.
- A identidade `ambiente.dependencias_sha256` difere da referência Docker anterior. Trata-se de um
  baseline novo na imagem registrada, não de comprovação de ambiente idêntico ou reprodução independente.
- O comparador de baselines retorna código 2 porque existem grupos novos; o relatório permite conferir
  que não houve perda ou alteração dos testes dos grupos compartilhados.
- Os 32 testes unitários do módulo de cobertura e do executor de controles passaram.
- Os cinco controles de regressão foram detectados; os originais foram restaurados.
- Preflight `AMP_PREFLIGHT_20261102T215732Z_75abfc2e`: 57 casos aprovados na preparação,
  zero tentativas de correção e nenhuma chamada à API. Configuração optativa:
  `config/execucao_cobertura_v2_preflight.yaml`.

Resumo com hashes e os cinco IDs liberados:
`outputs/cobertura_funcional/AMPLIACAO_20261102/resumo_ampliacao.json`.

## Comportamentos avaliados

| Grupo | Avaliação independente |
|---|---|
| `captcha_arithmetic` | Nove combinações de `*`, `+` e `-`, com resultados esperados explícitos, precedência, resposta persistida no banco e aceitação/recusa no endpoint de feedback; também rejeita ID inexistente. Controla somente a fonte aleatória durante a geração. |
| `zip_contents` | ZIP normal de duas entradas, nomes e bytes exatos (UTF-8 e binário), limpeza dos arquivos criados e erro para arquivo corrompido. Não exige preservar traversal. |
| `campaign_discount` | Pedido real com produtos e persistência, desconto e total finais, campanha com data incorreta, código desconhecido e ausência de campanha. Controla a data sem congelar timers de HTTP/streams. |

Os novos testes são externos ao alvo, versionados em `tests/functional/juice_shop/` e materializados
temporariamente pelo runner. Não alteram permanentemente o Juice Shop e não entram no scan SAST.
São testes F; o conjunto D existente não foi ampliado nem reclassificado.

## Entradas e evidências

- Revisão: `config/cobertura_funcional_v2.yaml`, schema de cobertura `1.0`.
- Mapa derivado: `config/mapa_testes_relacionados_v3.yaml`, schema de mapa `2.0`.
- Controles declarados: `config/controles_cobertura_v2.json`.
- Evidências: `outputs/cobertura_funcional/AMPLIACAO_20261102/`.
- Imagem usada nesta validação: `sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5`.

O número no nome do mapa identifica sua revisão; não altera o schema ou a política `relacionada_v2`.
A imagem instalada é registrada explicitamente e não substitui a identidade de imagens das campanhas
anteriores. O baseline novo pertence ao ambiente e à revisão novos.

## Verificação de regressões

Os controles alteram temporariamente uma única âncora no código original:

1. Substituir o resultado da conta do CAPTCHA por zero.
2. Omitir a persistência do CAPTCHA.
3. Omitir a extração dos arquivos do ZIP.
4. Omitir o desconto de campanha.
5. Aceitar a campanha ignorando sua data.

Cada controle exige aprovação do grupo no código original e falha do teste esperado no mutante.
Timeout, erro de infraestrutura e falha de outro teste não contam como detecção. A restauração confere
os bytes antes de escrever e recusa sobrescrever uma alteração desconhecida. Evidências parciais e
falhas são preservadas em saídas distintas.

O runner de controles possui testes unitários de restauração após exceções, proteção contra alteração
concorrente, âncora ambígua e rejeição de falsos sinais de detecção.

## Como reproduzir sem LLM

Execute na raiz do repositório, com o workspace Docker preparado. Use o ID da imagem registrado e
diretórios de saída novos; não rode os comandos simultaneamente, pois usam a mesma worktree.

```bash
TCC_DOCKER_IMAGE=sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5 \
docker compose run --rm --no-deps tcc .venv/bin/python \
  scripts/experimento/validar_controles_cobertura.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 \
  --revisao config/cobertura_funcional_v2.yaml \
  --mapa-testes config/mapa_testes_relacionados_v3.yaml \
  --controles config/controles_cobertura_v2.json \
  --saida outputs/cobertura_funcional/NOVA_RODADA/controles
```

```bash
TCC_DOCKER_IMAGE=sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5 \
docker compose run --rm --no-deps tcc .venv/bin/python \
  scripts/experimento/gerar_baseline_funcional.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 \
  --revisao config/cobertura_funcional_v2.yaml \
  --mapa-testes config/mapa_testes_relacionados_v3.yaml \
  --saida outputs/cobertura_funcional/NOVA_RODADA/baseline
```

```bash
TCC_DOCKER_IMAGE=sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5 \
docker compose run --rm --no-deps tcc .venv/bin/python \
  scripts/auditoria/auditar_cobertura_funcional.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 \
  --revisao config/cobertura_funcional_v2.yaml \
  --mapa-testes config/mapa_testes_relacionados_v3.yaml \
  --baseline-testes outputs/cobertura_funcional/NOVA_RODADA/baseline/baseline_testes.json \
  --saida outputs/cobertura_funcional/NOVA_RODADA/auditoria
```

A auditoria usa o baseline da própria revisão, não o baseline v1. O conjunto de casos só pode ser
considerado preparado depois que compilação, grupos obrigatórios e auditoria forem aprovados.

Para conferir a preparação dos casos selecionados, sem gerar correções:

```bash
TCC_DOCKER_IMAGE=sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5 \
docker compose run --rm --no-deps tcc .venv/bin/python executar.py \
  --config config/execucao_cobertura_v2_preflight.yaml
```

O YAML optativo mantém `modo: preflight` e K=1. Os comandos padrão continuam usando a revisão anterior.

## Lacunas seguintes

O plano de lacunas publicado pela nova auditoria determina o próximo incremento. Permanecem para
avaliação os comportamentos compartilhados de `server.ts`, extração de marcadores de desafios, chat,
seed TOTP, parser de legendas, empacotamento Grunt e arquivos de teste que são eles próprios alvos.
Esses últimos exigem preservar a independência do avaliador; executar apenas o teste modificado não
resolve a lacuna. Nenhum caso foi removido do catálogo para melhorar a contagem de cobertura.

| Arquivo ainda bloqueado | Casos |
|---|---:|
| `server.ts` | 12 |
| `lib/codingChallenges.ts` | 2 |
| `routes/chat.ts` | 1 |
| `data/static/users.yml` | 1 |
| `frontend/src/app/last-login-ip/last-login-ip.component.spec.ts` | 2 |
| `frontend/src/app/app.guard.spec.ts` | 1 |
| `views/promotionVideo.pug` | 1 |
| `Gruntfile.js` | 1 |
