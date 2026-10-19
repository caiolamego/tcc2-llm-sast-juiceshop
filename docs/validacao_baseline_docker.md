# Entrega — referência Docker padronizada

Data local: 19/10/2026. Sem chamadas à LLM, commit ou push.

O baseline oficial fica vinculado à imagem imutável em
[`docker/referencia.json`](../docker/referencia.json). Pessoas que reproduzem
esta versão devem importar a mesma imagem, junto da mesma revisão do repositório
e das evidências em `outputs/baselines/docker/oficial_v1/`.
Reconstruir a imagem por conta própria não garante o mesmo conteúdo instalado.

- Imagem: `sha256:8cdd44451de11d038c61353eb88b6286c9c5e4461dace97e5bfa4137bed337d5` (`linux/amd64`).
- Baseline: `outputs/baselines/docker/oficial_v1/BASELINE/baseline_testes.json`.
- SHA256 do baseline: `52ef071b1d8f35cf63e547c5d79cd03644e98656f907180a3d90089d16b46def`.
- Commit alvo: `f915bddd82790d0f3018902d36ae9b4241a5f51f`.
- 39 grupos, 484 testes aprovados e seis ignorados; compilações Angular e servidor aprovadas.
- Comparação com `DOCKER_V2`: 39/39 grupos equivalentes; apenas `dependencias_sha256` diferente no ambiente.
- Tempo observado do baseline: 378.87 s. Não é um benchmark entre máquinas.
- Testes unitários: 319 antes; 340 depois, também executados dentro da imagem.
- Preflight real sem geração: 52 casos, P1–P4, 208 prompts, K=5 e zero tentativas de correção.
- Evidência: `outputs/campanha_docker/AMP_PREFLIGHT_20261019T174514Z_fe15bc52/preflight.json` e métricas na pasta irmã com sufixo `_METRICAS`.
- 1566 arquivos históricos conferidos por SHA256, sem alterações.

## Preparação e integridade

O setup verifica os itens existentes e novos por conteúdo, permissões e links.
Novas cópias são preparadas em temporário irmão e promovidas só após conferência.
O reparo preserva o item divergente em `workspace/.recuperacao/` antes da promoção.
O mesmo lock do pipeline impede preparar worktrees em uso.

As cinco worktrees foram conferidas; a instalação parcial do frontend na `wt-4`
foi preservada e substituída por uma cópia íntegra da referência. Código alterado
ou commit divergente é recusado sem restauração automática.

O Make seleciona o ID oficial da imagem e confere a referência antes de abrir
o painel ou executar preflight, dry-run e correções. As configurações Docker
apontam para o baseline novo, mantendo o histórico intacto. Uma referência
existente não é recalculada nem sobrescrita automaticamente.

## Comandos executados

```bash
make test-unit PYTHON=.venv/bin/python
make docker-repair K=5
make docker-baseline
make docker-test
make docker-check
make docker-preflight PROVIDER=openai
git diff --check
```

A evidência estruturada desta verificação está em
[`validacao.json`](../outputs/baselines/docker/oficial_v1/validacao.json).

## Distribuição e limites

O mantenedor exporta uma vez, para arquivo fora do Git:

```bash
make docker-export ARQUIVO=/caminho/tcc2-ambiente.tar
```

Outra pessoa recebe o arquivo e a mesma revisão do repositório, confere o
SHA256 informado e importa:

```bash
make docker-import ARQUIVO=/caminho/tcc2-ambiente.tar
make docker-setup K=5
make docker-preflight
make docker-painel
```

Exportação/importação com arquivo real não foram executadas nesta entrega para
não ocupar vários GB adicionais; a seleção da imagem e os comandos foram
conferidos, e a imagem oficial está disponível localmente. Não houve publicação
em registro nem validação em um segundo computador. Isso ainda precisa ocorrer
na distribuição. Hardware, kernel e condições operacionais podem afetar tempos
ou testes mesmo usando a mesma imagem; divergências continuam sendo recusadas.

Os 26 casos com lacunas funcionais não foram liberados: padronizar o ambiente
não amplia a cobertura. O padrão continua nos 52 preparados, com cinco workers.
A campanha real permanece manual, usando o provedor do `.env`.
