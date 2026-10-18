#!/usr/bin/env bash
# Gera, UMA vez, os lockfiles do Juice Shop no commit fixado e grava em
# docker/juice-shop/. Eles travam as versões de todas as dependências npm da
# imagem (o Juice Shop não versiona lockfile: seu .npmrc tem package-lock=false).
#
# Roda no host, dentro de um container descartável com o mesmo Node e a mesma
# plataforma da imagem. Recusa sobrescrever lockfiles existentes: trocar o
# conjunto de dependências é uma decisão a registrar no caderno.
#
# Uso (na raiz do repositório):  bash docker/gerar_lockfiles.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESTINO="$RAIZ/docker/juice-shop"
NODE_IMAGE="${NODE_IMAGE:-node:24.14.0-bookworm@sha256:5a593d74b632d1c6f816457477b6819760e13624455d587eef0fa418c8d0777b}"
JUICESHOP_REPO="${JUICESHOP_REPO:-https://github.com/caiolamego/juice-shop-tcc}"
JUICESHOP_COMMIT="${JUICESHOP_COMMIT:-f915bddd82790d0f3018902d36ae9b4241a5f51f}"

if [ -e "$DESTINO/package-lock.json" ] || [ -e "$DESTINO/frontend/package-lock.json" ]; then
  echo "ERRO: lockfiles já existem em docker/juice-shop/. Não serão sobrescritos." >&2
  exit 1
fi
mkdir -p "$DESTINO/frontend"

docker run --rm --platform linux/amd64 \
  --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e npm_config_update_notifier=false -e npm_config_fund=false -e npm_config_audit=false \
  -v "$DESTINO:/saida" \
  "$NODE_IMAGE" bash -euo pipefail -c "
    git clone --quiet --no-checkout '$JUICESHOP_REPO' /tmp/js
    cd /tmp/js
    git -c advice.detachedHead=false checkout --quiet --detach '$JUICESHOP_COMMIT'
    test \"\$(git rev-parse HEAD)\" = '$JUICESHOP_COMMIT'
    npm install --package-lock-only --package-lock=true --ignore-scripts
    (cd frontend && npm install --package-lock-only --package-lock=true --ignore-scripts)
    cp package-lock.json /saida/package-lock.json
    cp frontend/package-lock.json /saida/frontend/package-lock.json
    printf '{\n  \"gerado_em_utc\": \"%s\",\n  \"node\": \"%s\",\n  \"npm\": \"%s\",\n  \"plataforma\": \"%s\",\n  \"juice_shop_commit\": \"%s\"\n}\n' \
      \"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\" \"\$(node --version)\" \"\$(npm --version)\" \"\$(uname -m)\" '$JUICESHOP_COMMIT' \
      > /saida/geracao.json
  "

echo "Lockfiles gravados em docker/juice-shop/:"
ls -l "$DESTINO/package-lock.json" "$DESTINO/frontend/package-lock.json" "$DESTINO/geracao.json"
cat "$DESTINO/geracao.json"
