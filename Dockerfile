# syntax=docker/dockerfile:1
#
# Ambiente único do TCC2: a mesma imagem para Caio, Matheus e banca.
# Guia de uso e decisões: docs/docker.md
#
# A imagem contém SOMENTE o ambiente (ferramentas, dependências Python e um
# Juice Shop de referência já instalado e compilado). O código do projeto é
# montado em /repo pelo compose.yaml, e os resultados caem em outputs/ do host.
#
# Plataforma fixa linux/amd64: dependências nativas do Juice Shop (sqlite3,
# esbuild) geram binários diferentes por arquitetura. Em Macs Apple Silicon a
# imagem roda por emulação (Rosetta), mais lenta, mas com os mesmos binários.

# Imagem base fixada pelo digest (o rótulo pode ser atualizado; o digest não).
# Plataforma linux/amd64 deste índice: sha256:1698b8f453a36aa5b2545a0ab21b1781bef5c62a4626a2e8d2a01e7cde4fad45
ARG NODE_IMAGE=node:24.14.0-bookworm@sha256:5a593d74b632d1c6f816457477b6819760e13624455d587eef0fa418c8d0777b
FROM --platform=linux/amd64 ${NODE_IMAGE}

ARG JUICESHOP_REPO=https://github.com/caiolamego/juice-shop-tcc
ARG JUICESHOP_COMMIT=f915bddd82790d0f3018902d36ae9b4241a5f51f

LABEL org.opencontainers.image.title="tcc2-llm-sast-juiceshop" \
      org.opencontainers.image.description="Ambiente reprodutível do pipeline LLM + SAST + testes (TCC2 UnB/FCTE)" \
      org.opencontainers.image.licenses="MIT" \
      br.unb.tcc2.juiceshop.commit="${JUICESHOP_COMMIT}"

# TZ=UTC: há teste do Juice Shop que falha em fusos negativos (caderno, F2.4).
# Semgrep sem checagem de versão e sem métricas: a execução não depende de rede.
ENV TZ=UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SEMGREP_ENABLE_VERSION_CHECK=0 \
    SEMGREP_SEND_METRICS=off \
    npm_config_update_notifier=false \
    npm_config_fund=false \
    npm_config_audit=false \
    PATH=/repo/.venv/bin:${PATH}

# A imagem oficial do Node (variante completa) já traz git, compiladores e
# Python 3.11; falta somente o módulo venv.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-venv \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /repo/workspace /opt/juice-shop \
 && touch /opt/ambiente.json \
 && chown -R node:node /repo /opt/juice-shop /opt/ambiente.json

# Usuário sem privilégios (uid 1000, já existe na imagem do Node).
USER node
RUN git config --global --add safe.directory '*' \
 && git config --global advice.detachedHead false

# ---------------------------------------------------------------------------
# Juice Shop de referência, no commit fixado, com dependências travadas pelos
# lockfiles versionados em docker/juice-shop/ (ver docker/gerar_lockfiles.sh).
# ---------------------------------------------------------------------------
WORKDIR /opt/juice-shop
RUN git clone --quiet --no-checkout "${JUICESHOP_REPO}" . \
 && git checkout --quiet --detach "${JUICESHOP_COMMIT}"

COPY --chown=node:node docker/juice-shop/package-lock.json ./package-lock.json
COPY --chown=node:node docker/juice-shop/frontend/package-lock.json ./frontend/package-lock.json

# O .npmrc do Juice Shop desliga o lockfile (package-lock=false); por isso o
# --package-lock=true explícito. O postinstall da raiz instalaria o frontend
# SEM lockfile (e o npm rebuild também o executa). Por isso ele é retirado do
# package.json só durante o npm ci, que roda normalmente os scripts de
# instalação das dependências (binários nativos de sqlite3, libxmljs2 etc.), e
# o arquivo é restaurado pelo git em seguida. É o único script de ciclo de
# vida da raiz; o frontend não tem nenhum.
RUN npm pkg delete scripts.postinstall \
 && npm ci --package-lock=true \
 && git checkout -- package.json \
 && test -z "$(git status --porcelain)" \
 && test ! -e frontend/node_modules

RUN cd frontend && npm ci --package-lock=true

# Mesmos passos do postinstall original, agora sobre dependências travadas.
RUN npm run build:frontend \
 && npm run build:server \
 && test -s build/server.js \
 && test -s frontend/dist/frontend/index.html

# O Juice Shop detecta que roda em container (/.dockerenv) e, com o padrão
# challenges.safetyMode=auto, DESLIGA 17 desafios marcados "disabledEnv: Docker"
# (XSS, SSTI, RCE, XXE, NoSQL...) e o código vulnerável deles (lib/utils.ts,
# data/static/challenges.yml). Fora de container, auto mantém todos ligados.
# "disabled" reproduz aqui o comportamento de uma máquina comum (opção oficial,
# a mesma de config/unsafe.yml). O pacote config aplica NODE_CONFIG por cima de
# config/test.yml, e identity.ambiente registra a variável (variaveis_sha256).
ENV NODE_CONFIG='{"challenges":{"safetyMode":"disabled"}}'

# ---------------------------------------------------------------------------
# Ambiente Python do projeto em /repo/.venv. O compose monta o repositório em
# /repo e cobre esta pasta com um volume anônimo inicializado a partir da
# imagem, para o .venv do host (outro sistema) nunca ser usado no container.
# ---------------------------------------------------------------------------
WORKDIR /repo
COPY --chown=node:node requirements.lock.txt /tmp/requirements.lock.txt
RUN python3 -m venv /repo/.venv \
 && /repo/.venv/bin/pip install --no-cache-dir --disable-pip-version-check -r /tmp/requirements.lock.txt

# Registro das versões efetivas, para conferência (cat /opt/ambiente.json).
RUN python3 - <<'EOF'
import hashlib, json, os, subprocess
def run(*cmd, **kw):
    return subprocess.check_output(cmd, text=True, **kw).strip()
def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()
ref = '/opt/juice-shop'
# Valor efetivo no ambiente dos testes (NODE_ENV=test), não só a variável.
safety = run('node', '-p', "require('config').get('challenges.safetyMode')",
             cwd=ref, env={**os.environ, 'NODE_ENV': 'test'})
if safety != 'disabled':
    raise SystemExit(f'challenges.safetyMode efetivo = {safety!r}; esperado disabled')
data = {
    'node_config': os.environ['NODE_CONFIG'],
    'juice_shop_safety_mode_efetivo': safety,
    'plataforma': run('uname', '-m'),
    'node': run('node', '--version'),
    'npm': run('npm', '--version'),
    'python': run('/repo/.venv/bin/python', '--version'),
    'semgrep': run('/repo/.venv/bin/semgrep', '--version'),
    'juice_shop_commit': run('git', '-C', ref, 'rev-parse', 'HEAD'),
    'package_lock_sha256': sha(f'{ref}/package-lock.json'),
    'frontend_package_lock_sha256': sha(f'{ref}/frontend/package-lock.json'),
    'requirements_lock_sha256': sha('/tmp/requirements.lock.txt'),
}
open('/opt/ambiente.json', 'w').write(json.dumps(data, indent=2, sort_keys=True) + '\n')
print(json.dumps(data, indent=2, sort_keys=True))
EOF

CMD ["bash"]
