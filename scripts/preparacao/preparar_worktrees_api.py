#!/usr/bin/env python3
"""Prepara artefatos API em worktrees existentes, sem instalação ou LLM."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: E402,F401
import argparse
import json
import subprocess
from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e06_aplicacao.worktrees import reservar_execucao
from pipeline.etapas.e07_validacao.preparacao_api import conferir, preparar


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origem', type=Path, required=True)
    parser.add_argument('--k', type=int, required=True)
    args = parser.parse_args(argv)
    if args.k < 1: parser.error('--k deve ser positivo')
    try:
        reservar_execucao(RAIZ_REPO)
        origem = args.origem.resolve()
        commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=origem, text=True).strip()
        worktrees = [RAIZ_REPO/f'workspace/wt-{i}' for i in range(1,args.k+1)]
        for wt in [origem, *worktrees]:
            if subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=wt,text=True).strip():
                raise ValueError('Worktree modificada: '+str(wt))
            if subprocess.check_output(['git','rev-parse','HEAD'],cwd=wt,text=True).strip()!=commit:
                raise ValueError('Commit divergente: '+str(wt))
        results = {wt.name:preparar(origem,wt) for wt in worktrees}
        for wt in worktrees: conferir(wt)
        print(json.dumps({'commit':commit,'worktrees':results},ensure_ascii=False,sort_keys=True,indent=2))
        return 0
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr);return 1


if __name__ == '__main__':raise SystemExit(main())
