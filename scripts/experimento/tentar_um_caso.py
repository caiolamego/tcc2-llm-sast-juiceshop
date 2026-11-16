#!/usr/bin/env python3
"""Uma tentativa ponta a ponta sobre um caso do catalogo por ocorrencia.

Atalho para o orquestrador com um caso, uma estrategia e K=1: preflight,
prompt, LLM (ou resposta falsa com --dry-run), patch, SAST depois e validacao,
com os mesmos artefatos de uma execucao em --saida.
"""
from __future__ import annotations

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402


import argparse
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso", required=True, help="ID AMP do caso")
    ap.add_argument("--estrategia", default="P1")
    ap.add_argument("--execucao", required=True, help="ID da execucao")
    ap.add_argument("--dry-run", action="store_true", help="resposta falsa, sem chamar a API")
    ap.add_argument('--catalogo', type=Path, required=True)
    ap.add_argument('--perfil-sast', type=Path)
    ap.add_argument('--semgrep-bin', default='semgrep')
    ap.add_argument('--saida', type=Path)
    ap.add_argument('--baseline-testes', type=Path, default=RAIZ_REPO/'outputs/baseline_testes.json')
    from pipeline.etapas.e07_validacao.politicas import argumentos, opcoes
    argumentos(ap)
    args = ap.parse_args()

    from pipeline.etapas.e02_catalogo.catalogo import carregar
    if not carregar(args.catalogo).ampliado:
        raise SystemExit('O catálogo histórico não é mais executável; use o catálogo por ocorrência '
                         '(tag git modo-historico-final para o modo antigo)')
    if not args.perfil_sast or not args.saida:
        raise SystemExit('Catálogo ampliado requer --perfil-sast e --saida')
    from pipeline.orquestracao.campanha import main as run
    argv = ['--execucao', args.execucao, '--catalogo', str(args.catalogo),
            '--perfil-sast', str(args.perfil_sast), '--saida', str(args.saida),
            '--semgrep-bin', args.semgrep_bin, '--casos', args.caso,
            '--estrategias', args.estrategia, '--k', '1', '--baseline-testes', str(args.baseline_testes)]
    for chave, valor in opcoes(args).items():
        if valor is not None:
            argv.extend(['--'+chave.replace('_','-'),str(valor)])
    if args.dry_run: argv.append('--dry-run')
    sys.argv = [sys.argv[0], *argv]
    run()


if __name__ == "__main__":
    main()
