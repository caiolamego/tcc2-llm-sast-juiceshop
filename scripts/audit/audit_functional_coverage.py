#!/usr/bin/env python3
"""Audita cobertura por ocorrência; não executa testes, scans ou LLM."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
import argparse
import json
from pipeline.validation.coverage_audit import auditar,publicar


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('catalogo','checkout','mapa-testes','revisao','saida'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--baseline-testes',type=Path)
    args=parser.parse_args(argv)
    try:
        artifacts,inputs,summary=auditar(args.catalogo,args.checkout,args.mapa_testes,args.revisao,args.baseline_testes)
        publicar(args.saida,artifacts,inputs)
        print(json.dumps(summary,ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
