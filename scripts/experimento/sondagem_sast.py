#!/usr/bin/env python3
"""Sondagem do oraculo R, sem LLM: aplica um patch num worktree alugado e
compara o scan antes e depois com o mesmo perfil, gate e comparador da
execucao (preflight.sondar). Opcionalmente roda a validacao.

Os patches marcados como ESCRITO_A_MAO NAO sao saida da LLM e nao entram em
nenhuma metrica do experimento.

Uso:
    python scripts/experimento/sondagem_sast.py --caso <AMP...> --patch <arquivo.diff> --rotulo <nome> \
        --origem ESCRITO_A_MAO --catalogo <catalogo_issues.json> --perfil-sast <perfil.json> --saida <pasta> [--validar]
"""
from __future__ import annotations

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402


import argparse
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso", required=True)
    ap.add_argument("--patch", required=True, help="diff aplicavel com 'git apply'")
    ap.add_argument("--rotulo", required=True, help="ID da sondagem (pasta em --saida)")
    ap.add_argument("--origem", required=True, choices=["LLM_ARQUIVADA", "ESCRITO_A_MAO"])
    ap.add_argument("--validar", action="store_true")
    ap.add_argument('--catalogo', type=Path, required=True)
    ap.add_argument('--perfil-sast', type=Path)
    ap.add_argument('--semgrep-bin', default='semgrep')
    ap.add_argument('--saida', type=Path)
    ap.add_argument('--baseline-testes', type=Path, default=RAIZ_REPO/'outputs/baseline_testes.json')
    from pipeline.etapas.e07_validacao.politicas import argumentos
    argumentos(ap)
    args = ap.parse_args()

    from pipeline.etapas.e02_catalogo.catalogo import carregar
    catalogo = carregar(args.catalogo)
    if not catalogo.ampliado:
        raise SystemExit('O catálogo histórico não é mais executável; use o catálogo por ocorrência '
                         '(tag git modo-historico-final para o modo antigo)')
    from pipeline.orquestracao.preflight import sondar
    sondar(args, catalogo)


if __name__ == "__main__":
    main()
