#!/usr/bin/env bash
# Prepara, DENTRO do container, o Juice Shop e as worktrees wt-1..wt-K no
# volume /repo/workspace, a partir do Juice Shop de referência da imagem
# (/opt/juice-shop). As dependências e os builds são cópias exatas da
# referência: mesmo conteúdo e mesmos hashes de ambiente em qualquer máquina.
#
# Não usa rede e não instala nada. Idempotente: worktrees já preparadas e
# limpas são mantidas; worktree alterada ou em outro commit é recusada.
#
# Uso:  make docker-setup          (K=4)
#       docker compose run --rm tcc bash docker/preparar_workspace.sh 4
set -euo pipefail

K="${1:-4}"
REF=/opt/juice-shop
WS=/repo/workspace
BARE="$WS/juice-shop.git"

if [ ! -d "$REF/.git" ] || [ ! -f /opt/ambiente.json ]; then
  echo "ERRO: rode este script dentro do container (docker compose run --rm tcc ...)." >&2
  exit 1
fi
case "$K" in ''|*[!0-9]*|0) echo "ERRO: K deve ser inteiro positivo." >&2; exit 1;; esac

COMMIT="$(git -C "$REF" rev-parse HEAD)"
echo "Juice Shop de referência: $COMMIT"

if [ ! -d "$BARE" ]; then
  echo "[1/3] Criando o repositório espelho em workspace/juice-shop.git"
  git clone --quiet --mirror "$REF" "$BARE"
fi

# Checkout limpo do alvo, sem dependências (feature 01): fonte do catálogo
# ampliado, das evidências em config/revisoes_associacoes_v1.yaml e de scripts
# de auditoria/testes que leem workspace/catalogo-alvo. Nunca é modificado.
ALVO="$WS/catalogo-alvo"
if [ ! -d "$ALVO" ]; then
  echo "[2/3] Criando o checkout limpo workspace/catalogo-alvo"
  git --git-dir="$BARE" worktree add --quiet --detach "$ALVO" "$COMMIT"
fi
if [ "$(git -C "$ALVO" rev-parse HEAD)" != "$COMMIT" ] || [ -n "$(git -C "$ALVO" status --porcelain --untracked-files=all)" ]; then
  echo "ERRO: workspace/catalogo-alvo não está limpo no commit $COMMIT." >&2
  exit 1
fi

for i in $(seq 1 "$K"); do
  WT="$WS/wt-$i"
  if [ ! -d "$WT" ]; then
    echo "[2/3] Criando a worktree wt-$i"
    git --git-dir="$BARE" worktree add --quiet --detach "$WT" "$COMMIT"
  fi
  HEAD_WT="$(git -C "$WT" rev-parse HEAD)"
  if [ "$HEAD_WT" != "$COMMIT" ]; then
    echo "ERRO: wt-$i está em $HEAD_WT, esperado $COMMIT." >&2
    exit 1
  fi
  for item in node_modules frontend/node_modules build frontend/dist package-lock.json frontend/package-lock.json; do
    if [ ! -e "$WT/$item" ]; then
      echo "[3/3] wt-$i: copiando $item da referência"
      cp -a "$REF/$item" "$WT/$item"
    fi
  done
  if [ -n "$(git -C "$WT" status --porcelain --untracked-files=all)" ]; then
    echo "ERRO: wt-$i tem alterações; não será usada." >&2
    git -C "$WT" status --short | head -20 >&2
    exit 1
  fi
done

echo "Pronto: $K worktree(s) limpa(s) em workspace/, no commit $COMMIT."
ls -d "$WS"/wt-*
