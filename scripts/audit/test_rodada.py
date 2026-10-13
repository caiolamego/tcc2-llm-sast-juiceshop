#!/usr/bin/env python3
"""Entrada comum para conferir regras, relatório ou integração de uma rodada."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402
import argparse
import json
import os
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rodada', type=int, choices=range(1, 13), required=True)
    parser.add_argument('--tipo', choices=('inventario', 'regras', 'relatorio', 'integracao'), default='inventario')
    parser.add_argument('--semgrep-bin', default='semgrep')
    parser.add_argument('--node-bin', default='node')
    parser.add_argument('--worktree', type=Path)
    parser.add_argument('--deps', type=Path)
    args = parser.parse_args()
    data = json.loads((RAIZ_REPO / f'tests/integration/rodada{args.rodada}/manifesto.json').read_text())
    if args.tipo == 'inventario':
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    env = os.environ.copy()
    if args.tipo == 'regras':
        cmd = [args.semgrep_bin, 'scan', '--test', str(RAIZ_REPO / data['regras'])]
    elif args.tipo == 'relatorio':
        if not data['teste_relatorio']:
            parser.error('Esta rodada não possui teste específico de relatório; execute make test-unit para os testes gerais.')
        cmd = [sys.executable, '-m', 'unittest', 'discover', '-s', str(RAIZ_REPO / 'tests/unit'), '-p', Path(data['teste_relatorio']).name]
    else:
        if not data['teste_integracao']:
            parser.error('Integração não implementada nesta rodada; nenhum teste foi executado.')
        if args.worktree is None or not args.worktree.is_dir():
            parser.error('--worktree deve apontar para um checkout existente do alvo')
        env['JUICE_SHOP_WORKTREE'] = str(args.worktree.resolve())
        if args.rodada >= 8:
            if args.deps is None or not args.deps.is_dir():
                parser.error('--deps deve apontar para as dependências da rodada')
            env[f'ROUND{args.rodada}_DEPS'] = str(args.deps.resolve())
        cmd = [args.node_bin, '--test', '--test-reporter=tap', str(RAIZ_REPO / data['teste_integracao'])]
    raise SystemExit(subprocess.run(cmd, cwd=RAIZ_REPO, env=env).returncode)


if __name__ == '__main__':
    main()
