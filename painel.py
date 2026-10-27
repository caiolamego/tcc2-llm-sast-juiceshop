#!/usr/bin/env python3
"""Painel local do pipeline: python painel.py, depois http://127.0.0.1:8765."""
from pathlib import Path
import subprocess
import sys

RAIZ = Path(__file__).resolve().parent


def main():
    python = RAIZ / '.venv/bin/python'
    if python.is_file() and Path(sys.prefix) != RAIZ / '.venv':
        try:
            return subprocess.run([str(python), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=RAIZ).returncode
        except KeyboardInterrupt:
            return 130
    sys.path.insert(0, str(RAIZ / 'src'))
    from pipeline.painel.servidor import main as servir
    return servir()


if __name__ == '__main__':
    raise SystemExit(main())
