# Cobertura funcional — segundo incremento, server.ts

Incremento de 02/11/2026 sobre a revisão v2. Resolve as duas lacunas que bloqueiam a seleção conjunta
dos 12 casos de `server.ts`: contratos dos recursos gerados e propagação/log de falhas no medidor de
inicialização. Não gera correções LLM nem modifica a campanha histórica.

## Resultado verificado

- Auditoria: **69 casos preparados e nove bloqueados**, das mesmas 78 ocorrências (antes: 57/21).
- Todos os **12 casos de server.ts** passaram de bloqueados para preparados; nenhum caso antes preparado
  foi perdido.
- Baseline completo: **44 grupos comparáveis, 524 testes aprovados e seis ignorados**; compilações de
  servidor e frontend aprovadas. Ignorados não são contados como executados.
- Os 42 grupos anteriores mantêm as mesmas identidades, estados e testes obrigatórios aprovados;
  os dois grupos adicionais são os desta revisão. O ambiente registrado é igual ao do incremento anterior.
- **14/14 controles de regressão detectados** na rodada revisada; os 32 testes unitários de cobertura
  e do executor de controles passaram.
- Preflight `AMP_PREFLIGHT_20261102T222154Z_6a78e537` concluído para **69 casos**, com zero tentativas
  de correção e nenhuma chamada à API.

O resumo com os 12 IDs liberados e os hashes das entradas e evidências está em
`outputs/cobertura_funcional/SERVER_20261102/resumo_bloco_server.json`.

A comparação com a revisão v2 está em `comparacao_com_v2.json`. O comparador retorna código 2 pela
presença dos dois grupos novos e pela identidade de cobertura ampliada; não houve diferença funcional
nos grupos compartilhados. A auditoria mantém as nove lacunas restantes em `auditoria/lacunas.json`
e `auditoria/plano_testes_adicionais.md`.

As nove ocorrências restantes estão em `lib/codingChallenges.ts` (duas), `routes/chat.ts` (uma),
`data/static/users.yml` (uma), testes de `last-login-ip` (duas), teste de `app.guard` (uma),
`views/promotionVideo.pug` (uma) e `Gruntfile.js` (uma). A revisão mantém esses casos bloqueados;
nenhuma ocorrência foi retirada do catálogo para aumentar a prontidão.

## Avaliações acrescentadas

`tests/functional/juice_shop/server_resources.test.ts` contém 21 testes independentes executados com
Express real, supertest e bancos de teste. Os 14 modelos do laço `autoModels` são exercitados em
operações permitidas, sem exigir preservar exploração de vulnerabilidades:

| Modelo | Contratos observados |
|---|---|
| User | Cadastro, listagem completa, exclusão de password/totpSecret e carteira automática; falha da criação da carteira é registrada sem interromper o cadastro. |
| Product | Criação, leitura, atualização, valores persistidos, tradução de nome/descrição em lista e leitura; exclusão recusada. |
| Feedback | Criação com CAPTCHA, conteúdo/rating persistidos, listagem e atualização recusada. |
| BasketItem | Criação, leitura, atualização e exclusão de item da cesta autenticada. |
| Challenge | Listagem completa, associação real de dependências e tradução com/sem sufixo de advertência. |
| Complaint | Criação e listagem autenticadas, conteúdo persistido e leitura individual recusada. |
| Recycle | Criação/persistência, recuperação e atualização recusada. |
| SecurityQuestion | Listagem e tradução de pergunta. |
| SecurityAnswer | Criação para o novo usuário, referência da pergunta, resposta transformada e listagem recusada. |
| Address | Criação, leitura, atualização e exclusão de endereço pertencente ao usuário. |
| PrivacyRequest | Criação/persistência e listagem recusada. |
| Card | Criação, vínculo do usuário, listagem mascarada e exclusão. |
| Quantity | Listagem completa e quantidade comparada ao banco. |
| Hint | Listagem completa, atualização persistida e tradução. |

A resposta dos recursos é conferida com `status`, `data` e tipo JSON. As operações são verificadas
contra registros efetivamente persistidos; não basta retornar HTTP 200. Os grupos existentes da
revisão v2 continuam na união por arquivo.

`tests/functional/juice_shop/server_startup.unit.test.ts` acrescenta três testes da função real
`collectDurationPromise`. O teste encontra sua declaração por AST TypeScript, transpila o inicializador
e o executa com gauge, console e tarefa controlados. Não copia o corpo da função para o avaliador.
Verifica argumentos, resultado e finalização única do timer no sucesso; nas falhas síncrona/assíncrona,
verifica log com nome da tarefa e erro e propagação da mesma exceção.

Isso cobre a função identificada na ocorrência, sem iniciar serviços e tarefas de customização.
Não demonstra recuperação de uma inicialização completa, temporização real do Prometheus ou cobertura
integral do servidor. Hooks de leitura bloqueados pelas regras de acesso não são liberados para teste.

## Revisões e evidências

- Revisão: `config/cobertura_funcional_v3.yaml`.
- Mapa derivado: `config/mapa_testes_relacionados_v4.yaml`, preservando schema `2.0`.
- Controles: `config/controles_cobertura_v3.json`.
- Configuração optativa: `config/execucao_cobertura_v3_preflight.yaml`, modo preflight e K=1.
- Evidências: `outputs/cobertura_funcional/SERVER_20261102/`.
- Imagem: `sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5`.

As revisões v1/v2, mapas, baselines, configurações e resultados anteriores são preservados. Os novos
testes são F; o conjunto D não foi alterado. A prontidão depende do baseline e da auditoria da própria
revisão, sem misturar baselines de identidades diferentes.

## Controles de regressão

Há 14 controles sobre uma âncora única de `server.ts`: omitir os recursos Hint, SecurityAnswer e
PrivacyRequest; omitir a carteira; retirar a exclusão de atributos; habilitar a paginação; omitir a
associação de dependências; retirar tradução de produto, descrição ou advertência; omitir log de
falha da carteira; omitir timer, log ou propagação de erro no medidor de startup.

Cada controle exige um grupo sadio aprovado e falha do teste nominalmente indicado, sem falha
operacional. Os arquivos originais são restaurados com verificação de bytes. Os comandos adquirem a
reserva da worktree e recusam destino existente.

A primeira rodada de controles identificou uma expectativa nominal inadequada para paginação: a
biblioteca usa limite de 100 registros. O teste de usuários tinha menos de 100 e continuou passando;
as listagens de desafios e dicas já detectavam o truncamento. O controle inicial foi registrado como
não detectado porque o teste esperado não falhou. A rodada revisada aponta explicitamente para o
teste de dicas; não passa a aceitar falha de qualquer teste. As rodadas iniciais permanecem arquivadas
como desenvolvimento, não como resultado final desta revisão.

## Reprodução sem LLM

Use o ID da imagem acima em `TCC_DOCKER_IMAGE` e saídas inéditas. Execute sequencialmente:

```bash
docker compose run --rm --no-deps tcc .venv/bin/python \
  scripts/experimento/validar_controles_cobertura.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 --revisao config/cobertura_funcional_v3.yaml \
  --mapa-testes config/mapa_testes_relacionados_v4.yaml \
  --controles config/controles_cobertura_v3.json \
  --saida outputs/cobertura_funcional/NOVA_RODADA_SERVER/controles
```

```bash
docker compose run --rm --no-deps tcc .venv/bin/python \
  scripts/experimento/gerar_baseline_funcional.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 --revisao config/cobertura_funcional_v3.yaml \
  --mapa-testes config/mapa_testes_relacionados_v4.yaml \
  --saida outputs/cobertura_funcional/NOVA_RODADA_SERVER/baseline
```

```bash
docker compose run --rm --no-deps tcc .venv/bin/python \
  scripts/auditoria/auditar_cobertura_funcional.py \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --checkout workspace/wt-1 --revisao config/cobertura_funcional_v3.yaml \
  --mapa-testes config/mapa_testes_relacionados_v4.yaml \
  --baseline-testes outputs/cobertura_funcional/NOVA_RODADA_SERVER/baseline/baseline_testes.json \
  --saida outputs/cobertura_funcional/NOVA_RODADA_SERVER/auditoria
```

O preflight optativo consulta o baseline publicado nesta revisão:

```bash
docker compose run --rm --no-deps tcc .venv/bin/python executar.py \
  --config config/execucao_cobertura_v3_preflight.yaml
```

Para reproduzir em outra pasta de evidências, use uma cópia da configuração que aponte ao baseline
gerado nessa pasta. O preflight não executa testes funcionais nem chama uma LLM; verifica a preparação.
