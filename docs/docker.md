# Rodar o projeto com Docker

O Docker garante que **todos** (autores, orientadora e banca) rodem o projeto com as mesmas versões e a mesma
configuração. As respostas da LLM continuam podendo variar entre execuções (isso é parte do objeto de estudo); o que
não pode variar é o ambiente em que elas são geradas e validadas.

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
  referência. Por isso os hashes de ambiente registrados pelo pipeline são os mesmos em qualquer máquina.

## Passo 0 — Instalar o Docker

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

## Passo 1 — Configurar o `.env`

O container lê o `.env` da raiz do repositório (ele nunca entra na imagem). Copie o modelo e preencha a chave:

```bash
cp .env.example .env
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

## Passo 5 — Conferir

```bash
make docker-ambiente
```
```bash
make docker-test
```
```bash
make docker-test-rules
```

## Passo 6 — Usar

| Comando | O que faz | Chama a LLM? |
|---|---|---|
| `make docker-painel` | Painel em http://127.0.0.1:8765 (abra no navegador do seu computador) | Só se você iniciar em modo Real |
| `make docker-preflight` | Prepara e confere tudo, monta os prompts | Não |
| `make docker-dry-run` | Pipeline completo com respostas simuladas | Não |
| `make docker-real` | Execução real configurada em `config/execucao.yaml` | **Sim** (limites do `.env`) |
| `make docker-shell` | Terminal dentro do container | — |

Os alvos `docker-preflight`, `docker-dry-run` e `docker-real` usam `config/execucao.yaml`. Para outro arquivo,
passe `CONFIG`, por exemplo `make docker-dry-run CONFIG=config/outro.yaml`.

Qualquer outro comando: `docker compose run --rm tcc <comando>`, por exemplo
`docker compose run --rm tcc python scripts/experiment/diagnose_llm.py --modo offline`.

## Baseline funcional do Docker

O baseline funcional (a referência do critério F) registra a identidade do ambiente em que foi gerado. Por isso, um
baseline gerado fora do Docker não vale dentro dele, e o preflight recusa com "Ambiente funcional diverge do baseline".
O baseline do Docker é `outputs/revalidacoes/DOCKER_V2/BASELINE/baseline_testes.json`. Ele foi gerado sem LLM e só
precisa ser refeito se a imagem mudar:

```bash
docker compose run --rm tcc python scripts/experiment/validate_functional_coverage.py --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json --checkout workspace/wt-1 --mapa-testes config/mapa_testes_relacionados_v2.yaml --revisao config/cobertura_funcional_v1.yaml --saida outputs/revalidacoes/<NOVA_PASTA>/BASELINE
```

Para conferir se um baseline novo se comporta como o anterior (0 = todos os grupos equivalentes, 2 = há diferença):

```bash
python3 scripts/audit/compare_functional_baselines.py --referencia outputs/revalidacoes/PILOTO10_CORRECAO_V1/BASELINE/baseline_testes.json --novo outputs/revalidacoes/<NOVA_PASTA>/BASELINE/baseline_testes.json --saida outputs/revalidacoes/<NOVA_PASTA>/comparacao_baseline_piloto10.json
```

## Cuidados

- **Execuções longas no Mac:** ligue na tomada e deixe a tampa aberta. O Docker Desktop não impede o Mac de dormir.
- **Não misture ambientes:** resultados e baselines gerados fora do Docker (no `.venv` local) têm outra identidade de
  ambiente e não devem ser misturados com execuções feitas no container.
- **Não remova o `NODE_CONFIG` da imagem** nem o sobrescreva com `-e NODE_CONFIG=...`: o Juice Shop voltaria a desligar
  desafios. O preflight recusa um ambiente com variáveis diferentes das do baseline.
- **Recomeçar as worktrees do zero:** `docker volume rm tcc2_workspace` e depois `make docker-setup`.
- **Imagem como referência:** para a banca reproduzir exatamente, a imagem construída deve ser publicada num registro
  (por exemplo, GitHub Container Registry) e citada pelo digest (`sha256:...`). Reconstruir a partir do `Dockerfile`
  pode trazer pacotes do sistema (apt) ligeiramente diferentes; as versões que importam (Node, Python, Semgrep, Juice
  Shop e dependências npm) continuam travadas.
