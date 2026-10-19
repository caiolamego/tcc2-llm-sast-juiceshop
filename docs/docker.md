# Rodar o projeto com Docker

A referência oficial é o par **imagem imutável + baseline funcional**, registrado
em `docker/referencia.json`. Todos devem carregar a mesma imagem e usar os mesmos
arquivos de baseline. Reconstruir o Dockerfile em cada computador pode produzir
binários diferentes e não substitui a distribuição dessa referência.

Os comandos de campanha conferem os hashes antes de abrir o painel ou executar
o pipeline. Não recalculam o baseline automaticamente e não relaxam seus gates.
As respostas da LLM e efeitos do hardware/runtime ainda podem variar; usar a
mesma imagem não prova equivalência de todo comportamento em qualquer máquina.

## O que fica igual para todos

| Item | Versão fixada | Onde é fixado |
|---|---|---|
| Sistema e plataforma | Debian 12 (bookworm), `linux/amd64` | `Dockerfile` (`FROM --platform=linux/amd64`) |
| Node.js / npm | 24.14.0 / o npm que acompanha essa imagem | `Dockerfile` (`NODE_IMAGE`) |
| Python | 3.11 da imagem | `Dockerfile` |
| Pacotes Python, incluindo Semgrep 1.177.0 | versões exatas | `requirements.lock.txt` |
| OWASP Juice Shop | commit `f915bddd82790d0f3018902d36ae9b4241a5f51f` | `Dockerfile` (`JUICESHOP_COMMIT`) |
| Dependências npm do Juice Shop (servidor e frontend) | versões exatas | `docker/juice-shop/package-lock.json` e `docker/juice-shop/frontend/package-lock.json` |
| Fuso horário | UTC | `Dockerfile` e `compose.yaml` |
| Modo de segurança do Juice Shop | `challenges.safetyMode = disabled` (todos os desafios ligados) | `Dockerfile` (`NODE_CONFIG`) |

As versões efetivas de cada imagem ficam registradas em `/opt/ambiente.json` dentro do container
(`make docker-ambiente`).

**Por que `safetyMode = disabled`:** quando percebe que está num container, o Juice Shop desliga sozinho 17 desafios
perigosos (XSS, SSTI, RCE, XXE, NoSQL...) e o código vulnerável deles. Numa máquina comum, nada disso acontece. Sem a
correção, o alvo no Docker seria outro: 10 testes do baseline funcional mudavam de resultado. Com ela, o baseline do
Docker é equivalente ao do piloto nos 39 grupos. Detalhes no caderno, entrada de 2026-10-18.

**Por que `linux/amd64` mesmo em Mac com Apple Silicon:** o Juice Shop tem dependências com binários nativos
(`sqlite3`, `esbuild`), que mudam conforme a arquitetura do processador. Fixar uma única plataforma faz todo mundo
executar os mesmos binários. Em Macs Apple Silicon a imagem roda por emulação (Rosetta): funciona, mas é mais lenta.

**Como as peças se encaixam:**

- A **imagem** contém só o ambiente: ferramentas, pacotes Python e um Juice Shop de referência já instalado e
  compilado em `/opt/juice-shop`.
- O **código do projeto não fica na imagem**: a pasta do repositório é montada em `/repo`. Você edita no seu
  computador e os resultados aparecem direto em `outputs/`.
- O **`.venv` do seu computador não é usado** no container: um volume cobre `/repo/.venv` com o ambiente Python da
  imagem.
- As **worktrees `wt-1..wt-K`** ficam num volume do Docker (`tcc2_workspace`), criadas como cópias exatas da
  referência. O setup confere o conteúdo contra a imagem e recusa cópias divergentes ou incompletas.

## Passo 0 — Instalar o Docker

Os atalhos usam Docker Compose, Make e Python 3.9 ou superior no computador.
O Python do pipeline continua vindo da imagem; o script do host usa somente
a biblioteca padrão.

### macOS (Apple Silicon ou Intel)

1. Baixe o **Docker Desktop** em https://www.docker.com/products/docker-desktop/ (escolha "Apple Silicon" ou "Intel",
   conforme o seu Mac) e instale arrastando para Aplicativos.
2. Abra o Docker Desktop uma vez e aceite os termos. Espere o ícone da baleia na barra de menus ficar estável.
3. Em **Settings → General**, deixe marcado **"Use Rosetta for x86_64/amd64 emulation on Apple Silicon"** (só em Mac
   Apple Silicon).
4. Em **Settings → Resources**, recomendação para 16 GB de RAM: **8 CPUs, 10 GB de memória, 64 GB de disco**. Clique em
   **Apply & restart**.
5. Confira no terminal:
   ```bash
   docker --version
   ```
   ```bash
   docker compose version
   ```
   ```bash
   docker run --rm hello-world
   ```

### Linux

Instale o Docker Engine e o plugin Compose pela documentação oficial (https://docs.docker.com/engine/install/) e
adicione seu usuário ao grupo `docker`. O container roda como o usuário `node` (uid 1000): se o seu uid for outro,
arquivos criados em `outputs/` podem ficar com outro dono.

### Windows

Docker Desktop com WSL 2. Clone o repositório **dentro** do sistema de arquivos do WSL e rode os comandos por lá.

## Reproduzir a referência oficial (autores e banca)

Receba o arquivo da imagem exportada pelo mantenedor e a mesma revisão do
repositório, incluindo `docker/referencia.json` e
`outputs/baselines/docker/oficial_v1/`. Depois:

```bash
make docker-import ARQUIVO=/caminho/tcc2-ambiente.tar
make docker-check
make docker-setup K=4
make docker-preflight
make docker-painel
```

O Make usa o **ID da imagem registrado**, em vez de confiar na tag `:1.0`.
O import confere que a imagem oficial está disponível; o check também confere
baseline, evidências, comparação funcional e entradas do experimento. A chave
LLM continua no `.env` de cada pessoa. Não é distribuída dentro da imagem.

O painel padrão usa `config/execucao_docker_preparados.yaml`, com quatro workers
e os 52 casos preparados. Os 26 casos com lacunas permanecem no catálogo, mas
bloqueiam a seleção dos 78 na política atual.

## Preparar uma nova referência (somente mantenedor)

Os passos de construção abaixo produzem uma referência candidata. Uma imagem
reconstruída não ganha status oficial só por manter a mesma tag.

## Passo 1 — Configurar o `.env`

O container lê o `.env` da raiz do repositório (ele nunca entra na imagem). Somente se ainda não existir, copie o modelo e preencha a chave:

```bash
cp -n .env.example .env
```

## Passo 2 — Lockfiles do Juice Shop (só se ainda não existirem)

Os lockfiles em `docker/juice-shop/` já fazem parte do repositório. **Só gere de novo se eles não existirem**; trocar as
dependências é uma decisão metodológica a registrar no caderno.

```bash
make docker-lockfiles
```

## Passo 3 — Construir a imagem

Demora na primeira vez (instala e compila o Juice Shop; com emulação, pode passar de 30 minutos). Depois, o Docker
reaproveita as camadas.

```bash
make docker-build
```

## Passo 4 — Preparar as worktrees

Cria `wt-1..wt-4` no volume, sem rede e sem instalar nada:

```bash
make docker-setup K=4
```

## Passo 5 — Gerar e congelar o baseline uma vez

```bash
make docker-baseline
```

Este comando executa todos os grupos funcionais revisados em `wt-1`, sem LLM,
e publica em `outputs/baselines/docker/oficial_v1/BASELINE/`. Em seguida,
compara com `DOCKER_V2`, verifica ambiente, integridade, grupos e compilações,
e cria `docker/referencia.json` sem sobrescrever referências existentes.
Uma divergência funcional impede o congelamento e preserva o candidato.

Se um candidato foi interrompido, investigue seus resultados; o comando não o
apaga nem o substitui. Para congelar um candidato já concluído, após corrigir
a causa e conferir os resultados:

```bash
python3 docker/referencia.py congelar --baseline outputs/baselines/docker/oficial_v1/BASELINE/baseline_testes.json
```

Referência já publicada e íntegra não dispara novos testes. Outra versão de
imagem, entradas ou validação exige uma nova referência explícita; nenhuma
campanha troca automaticamente para o novo ambiente.

Para distribuir o mesmo ambiente (não faz push nem publica dados):

```bash
make docker-export ARQUIVO=/caminho/tcc2-ambiente.tar
```

Compartilhe esse arquivo, seu SHA256 exibido e a revisão do repositório que
contém o manifesto e todas as evidências do baseline. **Não versione o arquivo
da imagem no Git.** Na outra máquina, use `docker-import`, sem reconstruir.
Também é possível publicar a imagem em registro e fixar seu digest; essa
publicação é um procedimento separado e não é executada pelos comandos aqui.

## Passo 6 — Conferir

```bash
make docker-ambiente
```
```bash
make docker-test
```
```bash
make docker-test-rules
```

## Passo 7 — Usar

| Comando | O que faz | Chama a LLM? |
|---|---|---|
| `make docker-painel` | Painel em http://127.0.0.1:8765 (abra no navegador do seu computador) | Só se você iniciar em modo Real |
| `make docker-preflight` | Prepara e confere tudo, monta os prompts | Não |
| `make docker-dry-run` | Pipeline completo com respostas simuladas | Não |
| `make docker-real` | Execução real na configuração Docker escolhida | **Sim** (limites do `.env`) |
| `make docker-shell` | Terminal dentro do container | — |

Os alvos `docker-preflight`, `docker-dry-run`, `docker-real` e `docker-painel` usam `config/execucao_docker_preparados.yaml` por padrão. Para outro arquivo,
passe `CONFIG`, por exemplo `make docker-dry-run CONFIG=config/outro.yaml`.

Qualquer outro comando: `docker compose run --rm tcc <comando>`, por exemplo
`docker compose run --rm tcc python scripts/experiment/diagnose_llm.py --modo offline`.

## Campanha ampliada pelo painel (OpenAI, K=4)

Use `PROVIDER=openai` para selecionar OpenAI no processo do container, mesmo
quando o `.env` pessoal ainda contém `LLM_PROVIDER=colab`. A chave, o modelo e
os limites OpenAI continuam vindo do `.env`; o arquivo pessoal não é alterado.
Não copie o exemplo por cima de um `.env` já preenchido.

Há duas configurações novas, ambas com P1–P4, quatro worktrees, política
`relacionada_v2`, cache de validação desligado e baseline oficial congelado:

| Configuração | Seleção | Situação |
|---|---|---|
| `config/execucao_docker_78.yaml` | Todos os 78 casos, incluindo falsos positivos e inconclusivos | O gate atual recusa a seleção por lacunas funcionais em 26 casos |
| `config/execucao_docker_preparados.yaml` | 52 casos com revisão suficiente na união por arquivo | Subconjunto explícito, sujeito à validação do ambiente pelo preflight |

Os 26 casos não foram excluídos do catálogo. Resolver suas lacunas e verificar
os baselines é necessário para iniciar todos os 78 com essa política. Docker
padroniza o ambiente, mas não cria as evidências funcionais que faltam. Não
troque a política nem desative o gate apenas para liberar a campanha.

Prepare o ambiente uma vez, sem executar a LLM:

```bash
make docker-build
make docker-setup K=4
make docker-baseline
```

Para conferir o bloqueio dos 78 sem geração:

```bash
make docker-preflight CONFIG=config/execucao_docker_78.yaml PROVIDER=openai
```

Se optar por iniciar primeiro o subconjunto preparado, confira-o e abra o painel:

```bash
make docker-preflight CONFIG=config/execucao_docker_preparados.yaml PROVIDER=openai
make docker-painel CONFIG=config/execucao_docker_preparados.yaml PROVIDER=openai
```

Abra http://127.0.0.1:8765 e confira os 52 IDs, K=4 e provedor OpenAI antes de
iniciar em modo Real. Há até 208 posições caso/estratégia nesse subconjunto
e 312 nos 78; a parada por aceite pode reduzir as chamadas. Os limites de
chamadas e orçamento são acumulados: revise-os no `.env` antes da campanha,
sem presumir que o orçamento restante cobre a seleção inteira.

Os resultados novos ficam em `outputs/campanha_docker/`, no computador.
O piloto de dez casos e a configuração padrão continuam disponíveis.
Não execute simultaneamente dois painéis/pipelines sobre o mesmo workspace.

## Cópias incompletas e recuperação

O setup calcula hashes de arquivos, permissões e links tanto na imagem quanto
nas worktrees. Diretórios existentes também são verificados. Cada item novo é
copiado para um temporário irmão, conferido e só então promovido. Uma falha de
espaço não publica um diretório parcial como instalação válida.

Para reparar conteúdo divergente, com o pipeline e o painel encerrados:

```bash
make docker-repair K=4
```

O reparo primeiro prepara uma cópia íntegra; só depois move a pasta anterior
para `workspace/.recuperacao/<id>/`, registra sua origem e promove a nova.
Não restaura alterações de código e não remove os backups automaticamente.
Requer espaço para a cópia e o conteúdo preservado. Setup e reparo usam o
mesmo lock de workspace do pipeline.

## Histórico e limites

`DOCKER_V2` permanece arquivado e não é alterado. Em 19/10/2026 a imagem local
apresentou outro hash nas dependências do servidor, apesar das versões iguais;
a `wt-4` também continha uma cópia parcial do frontend após esgotar o disco.
Por isso, ignorar o gate ou editar hashes do baseline não seria uma solução.
O novo fluxo confere cópias e congela explicitamente a referência validada.

Não use um baseline novo para legitimar uma instalação incompleta. Uma mudança
funcional na comparação exige investigação, não publicação automática.

## Cuidados

- **Execuções longas no Mac:** ligue na tomada e deixe a tampa aberta. O Docker Desktop não impede o Mac de dormir.
- **Não misture ambientes:** resultados e baselines gerados fora do Docker (no `.venv` local) têm outra identidade de
  ambiente e não devem ser misturados com execuções feitas no container.
- **Não remova o `NODE_CONFIG` da imagem** nem o sobrescreva com `-e NODE_CONFIG=...`: o Juice Shop voltaria a desligar
  desafios. O preflight recusa um ambiente com variáveis diferentes das do baseline.
- **Recomeçar o workspace:** não remova o volume sem conferir os dados; prefira `make docker-repair` para dependências divergentes.
- **Imagem como referência:** para a banca reproduzir exatamente, distribua a imagem exportada e confira seu ID, ou publique-a num registro
  (por exemplo, GitHub Container Registry) e cite seu digest (`sha256:...`). Reconstruir a partir do `Dockerfile`
  pode trazer pacotes do sistema (apt) ligeiramente diferentes; as versões que importam (Node, Python, Semgrep, Juice
  Shop e dependências npm) continuam travadas.

Referências: [identidade e digest de imagens](https://docs.docker.com/reference/cli/docker/image/pull/)
e [exportação com docker image save](https://docs.docker.com/reference/cli/docker/image/save/).

Evidências desta versão: [validação do baseline Docker](validacao_baseline_docker.md).
