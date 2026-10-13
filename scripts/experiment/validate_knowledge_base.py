#!/usr/bin/env python3
"""Valida por leitura a base ou publica um manifesto novo sem sobrescrita."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401
import argparse
from pipeline.caminhos import RAIZ_REPO
from pipeline.rag.retriever import carregar_base, publicar_manifesto


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=RAIZ_REPO/'knowledge_base')
    ap.add_argument('--publicar-manifesto',action='store_true')
    a=ap.parse_args()
    try:
        if a.publicar_manifesto: publicar_manifesto(a.base)
        base=carregar_base(a.base)
    except (ValueError,OSError,TypeError) as exc:
        ap.exit(1,f'ERRO: {exc}\n')
    print(f'Base {base.manifesto["base_versao"]}: {len(base.corpos)} documentos; SHA-256 {base.hash_base}')


if __name__=='__main__':main()
