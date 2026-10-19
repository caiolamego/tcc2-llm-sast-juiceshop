#!/usr/bin/env bash
# Compatibilidade: preparação atômica e verificada, incluindo instalações existentes.
set -euo pipefail
exec python /repo/docker/workspace.py "$@"
