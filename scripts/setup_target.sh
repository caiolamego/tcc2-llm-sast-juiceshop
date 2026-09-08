#!/usr/bin/env bash
# Prepara o alvo: clone espelhado + pool de worktrees com node_modules.
set -euo pipefail

source .env
K="${1:-4}"                       # numero de worktrees no pool
BARE="workspace/juice-shop.git"

mkdir -p workspace

if [ ! -d "$BARE" ]; then
  echo "[1/4] Clonando o alvo (espelho)..."
  git clone --mirror "$JUICESHOP_REPO" "$BARE"
else
  echo "[1/4] Espelho ja existe; atualizando..."
  git --git-dir="$BARE" fetch --all --tags --prune
fi

echo "[2/4] Fixando o commit $JUICESHOP_COMMIT"
git --git-dir="$BARE" cat-file -e "${JUICESHOP_COMMIT}^{commit}" \
  || { echo "ERRO: commit nao encontrado no espelho"; exit 1; }

for i in $(seq -w 1 "$K"); do
  WT="workspace/wt-$i"
  if [ ! -d "$WT" ]; then
    echo "[3/4] Criando worktree $WT"
    git --git-dir="$BARE" worktree add --detach "$(pwd)/$WT" "$JUICESHOP_COMMIT"
  fi
done

for i in $(seq -w 1 "$K"); do
  WT="workspace/wt-$i"
  if [ ! -d "$WT/node_modules" ]; then
    echo "[4/4] Instalando dependencias em $WT (demora)..."
    ( cd "$WT" && npm ci --no-audit --no-fund )
  fi
done

echo "Pronto. Pool com $K worktrees em workspace/."