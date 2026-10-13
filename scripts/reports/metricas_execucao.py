#!/usr/bin/env python3
"""Metricas de uma execucao nas tres definicoes de F (protocolo, Secao 13).

Interface histórica; funções delegadas a pipeline.metrics. Novos CSVs usam consolidate_metrics.py.
Formulas da F7 do guia: TRV = sum(R*F*M)/m, TRI = sum(R)/m, TPF = sum(F)/m,
TNINI = sum(M)/m, TAP = sum(aplicavel)/m. Tentativa nao aplicada conta 0 em R,
F e M. TCD = aceitas que derrubam >= 1 teste de D / aceitas.

Cadeia por definicao: tentativas do desenho (P1, P2, ...) de um caso entram ate
a primeira aceita NAQUELA definicao (inclusive); as posteriores saem, como se a
cadeia tivesse parado ali. Condicoes de diagnostico (P1L) sao reportadas a parte.

Linhas antigas (E01, sem F_*): F_sem_separacao = F; marcador e criterio sao
reclassificados a partir de testes_falhos_novos. Se a escada parou numa camada
que so falhou por testes de D daquela definicao, as camadas seguintes nao
rodaram e o F reclassificado fica marcado como incompleto.

Uso:
    python scripts/reports/metricas_execucao.py E02
"""
from __future__ import annotations

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402


import json
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = RAIZ_REPO
from pipeline.validation.conjunto_d import classificar  # noqa: E402

DEFS = ("sem_separacao", "marcador", "criterio")
ORDEM_TIERS = ["T0", "T2", "T3", "T4"]


def carregar(execucao: str, saida: Path = RAIZ / "outputs") -> list[dict]:
    arq = saida / "resultados_consolidados" / "execucoes.jsonl"
    linhas = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [l for l in linhas if l["execucao"] == execucao]


# API pública histórica preservada por delegação.
from pipeline.metrics.normalizer import normalizar
from pipeline.metrics.calculator import v, indices, cadeia, custos


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('execucao')
    ap.add_argument('--saida', type=Path, default=RAIZ / 'outputs')
    args = ap.parse_args()
    execucao = args.execucao
    linhas = [normalizar(l) for l in carregar(execucao, args.saida)]
    for l in linhas:
        l["estrategia_curta"] = l["tentativa_id"].split("_")[3]
    desenho = [l for l in linhas if l["condicao"] == "desenho"]
    diag = [l for l in linhas if l["condicao"] == "diagnostico"]
    ordem = sorted({l["estrategia_curta"] for l in desenho}, key=lambda e: ("P1", "P2", "P3", "P4").index(e))
    casos = sorted({l["caso_id"] for l in linhas})

    res = {"AVISO": "Tentativa nao aplicada/indeterminada permanece no denominador e nao representa remediacao validada. Indeterminadas sao reportadas separadamente.",
           "execucao": execucao, "casos": len(casos), "definicoes": {}}
    for d in DEFS:
        cad = cadeia(desenho, d, ordem)
        aceitos = sorted({l["caso_id"] for l in cad if l[f"classificacao_{d}"] == "aceita"})
        res["definicoes"][d] = {
            "geral_por_tentativa": indices(cad, d),
            "por_estrategia": {e: indices([l for l in cad if l["estrategia_curta"] == e], d) for e in ordem},
            "por_caso": {"casos_aceitos": aceitos, "TRV_caso": round(len(aceitos) / len(casos), 4) if casos else None},
            "diagnostico_P1L": indices(diag, d) if diag else None,
        }
    tabela = []
    for caso in casos:
        ls = sorted([l for l in linhas if l["caso_id"] == caso],
                    key=lambda x: (x["condicao"] != "desenho", x["estrategia_curta"]))
        tabela.append({"caso": caso, "sigla": ls[0]["sigla_vuln"], "faixa": ls[0].get("faixa_regra"),
                       "tentativas": [{
                           "estrategia": l["estrategia_curta"], "condicao": l["condicao"],
                           "aplicacao": l["status_aplicacao"], "R": l["R"], "M": l["M"],
                           **{f"F_{d}": l[f"F_{d}"] for d in DEFS},
                           **{f"classificacao_{d}": l[f"classificacao_{d}"] for d in DEFS},
                           "tier_falha": l.get("tier_falha"),
                           "n_d_marcador": len(l["testes_falhos_d_marcador"]),
                           "n_d_criterio": len(l["testes_falhos_d_criterio"]),
                           "do_cache": l.get("do_cache"),
                       } for l in ls]})
    res["tabela"] = tabela
    res["custo"] = custos(linhas)
    arq_s = args.saida / "resultados_consolidados" / f"{execucao}_sessoes.json"
    if arq_s.exists():
        res["sessoes"] = [{k: s.get(k) for k in ("inicio", "fim", "duracao_s", "abortada")}
                          for s in json.loads(arq_s.read_text(encoding="utf-8"))]
    saida = args.saida / "resultados_consolidados" / f"{execucao}_metricas.json"
    saida.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{execucao}: {len(casos)} casos, {len(linhas)} tentativas ({len(diag)} de diagnostico)")
    print(f"{'definicao':14} {'m':>3} {'TRV':>6} {'TRI':>6} {'TPF':>6} {'TNINI':>6} {'TAP':>6} {'TCD':>6} {'casos aceitos'}")
    def fmt(value):
        return '-' if value is None else f'{value:.3f}'
    for d in DEFS:
        g = res["definicoes"][d]["geral_por_tentativa"]
        pc = res["definicoes"][d]["por_caso"]
        tcd = "-" if g["TCD"] is None else f"{g['TCD']:.2f}"
        print(f"{d:14} {g['m']:>3} {g['TRV']:>6.3f} {fmt(g['TRI']):>6} {fmt(g['TPF']):>6} {fmt(g['TNINI']):>6} "
              f"{g['TAP']:>6.3f} {tcd:>6} {len(pc['casos_aceitos'])}/{len(casos)} {pc['casos_aceitos']}"
              + (f"  [{g['indeterminadas']} indeterminada(s)]" if g["indeterminadas"] else ""))
    print("custo:", res["custo"])
    print("->", saida.resolve())


if __name__ == "__main__":
    main()
