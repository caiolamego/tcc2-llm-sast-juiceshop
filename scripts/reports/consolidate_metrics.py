#!/usr/bin/env python3
"""Consolida registros e evidências offline em JSON/CSV, sem sobrescrita."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
import argparse
from pipeline.metrics.loader import carregar
from pipeline.metrics.calculator import calcular
from pipeline.metrics.rris import carregar_pesos, calcular_rris
from pipeline.metrics.exporter import construir, publicar


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('execucao','entrada','catalogo','saida'):
        ap.add_argument('--'+key,required=True,type=str if key=='execucao' else Path)
    ap.add_argument('--definicao-f',choices=('criterio','marcador','sem_separacao'),default='criterio')
    ap.add_argument('--evidencia-rris',type=Path)
    ap.add_argument('--politica-pesos',type=Path)
    args=ap.parse_args(argv)
    try:
        entrada=carregar(args.entrada,args.execucao,args.catalogo)
        pesos=carregar_pesos(args.politica_pesos,entrada)
        report=calcular(entrada,args.definicao_f,pesos)
        report['RRIS']=calcular_rris(args.evidencia_rris,entrada,args.definicao_f)
        # Fontes opcionais registradas pelo leitor RRIS pertencem ao relatório também.
        report['proveniencia']['fontes_sha256']=dict(sorted(entrada.fontes.items()))
        artifacts=construir(report,entrada)
        publicar(args.saida,artifacts,entrada)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        ap.exit(1,f'ERRO: {exc}\n')
    print(f'{args.execucao}: {len(entrada.linhas)} tentativas; {len(artifacts)} artefatos publicados em {args.saida}')
    return 0


if __name__=='__main__':raise SystemExit(main())
