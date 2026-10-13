#!/usr/bin/env python3
"""Metricas de uma execucao nas tres definicoes de F (protocolo, Secao 13).

Calculo anterior a F7 (src/pipeline/metrics/calculator.py ainda nao existe).
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


def carregar(execucao: str) -> list[dict]:
    arq = RAIZ / "outputs" / "resultados_consolidados" / "execucoes.jsonl"
    linhas = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [l for l in linhas if l["execucao"] == execucao]


def normalizar(l: dict) -> dict:
    """Garante F_<def>, classificacao_<def>, testes_falhos_d_<def> e incompleto_<def>."""
    l = dict(l)
    l.setdefault("condicao", "desenho")
    if "F_criterio" in l:
        for d in DEFS:
            l[f"incompleto_{d}"] = False
        l.setdefault("testes_falhos_d_sem_separacao", [])
        return l
    # Linha antiga: reclassificacao a posteriori.
    l["F_sem_separacao"] = l["F"]
    l["testes_falhos_d_sem_separacao"] = []
    l["incompleto_sem_separacao"] = False
    c = classificar(l.get("testes_falhos_novos") or [])
    for d in ("marcador", "criterio"):
        l[f"testes_falhos_d_{d}"] = c[f"d_{d}"]
        if l["status_aplicacao"] != "aplicado":
            l[f"F_{d}"] = None
            l[f"incompleto_{d}"] = False
            continue
        tf = l.get("tier_falha")
        so_d = bool(l.get("testes_falhos_novos")) and not c[f"f_{d}"]
        if tf is None:
            l[f"F_{d}"], l[f"incompleto_{d}"] = 1, False
        elif so_d:
            # A camada que reprovou so tinha testes de D; se havia camadas
            # depois dela, elas nao rodaram.
            ultima = "T4"
            l[f"F_{d}"] = 1 if tf == ultima else None
            l[f"incompleto_{d}"] = tf != ultima
        else:
            l[f"F_{d}"], l[f"incompleto_{d}"] = 0, False
    for d in DEFS:
        f = l[f"F_{d}"]
        if l["status_aplicacao"] != "aplicado":
            l[f"classificacao_{d}"] = l["classificacao_final"]
        elif f is None:
            l[f"classificacao_{d}"] = "indeterminada"
        else:
            l[f"classificacao_{d}"] = ("aceita" if l["R"] and f and l["M"] else f"rejeitada:R{l['R']}F{f}M{l['M']}")
    return l


def v(x):
    return x or 0


def indices(ls: list[dict], d: str) -> dict | None:
    m = len(ls)
    if not m:
        return None
    aceitas = [l for l in ls if l[f"classificacao_{d}"] == "aceita"]
    return {
        "m": m,
        "TRV": round(sum(v(l["R"]) * v(l[f"F_{d}"]) * v(l["M"]) for l in ls) / m, 4),
        "TRI": round(sum(v(l["R"]) for l in ls) / m, 4),
        "TPF": round(sum(v(l[f"F_{d}"]) for l in ls) / m, 4),
        "TNINI": round(sum(v(l["M"]) for l in ls) / m, 4),
        "TAP": round(sum(l["status_aplicacao"] == "aplicado" for l in ls) / m, 4),
        "aceitas": len(aceitas),
        "TCD": (round(sum(bool(l[f"testes_falhos_d_{d}"]) for l in aceitas) / len(aceitas), 4)
                if aceitas else None),
        "indeterminadas": sum(1 for l in ls if l.get(f"incompleto_{d}")),
    }


def cadeia(ls: list[dict], d: str, ordem: list[str]) -> list[dict]:
    por_caso = defaultdict(list)
    for l in ls:
        por_caso[l["caso_id"]].append(l)
    saida = []
    for caso in sorted(por_caso):
        for l in sorted(por_caso[caso], key=lambda x: ordem.index(x["estrategia_curta"])):
            saida.append(l)
            if l[f"classificacao_{d}"] == "aceita":
                break
    return saida


def main() -> None:
    execucao = sys.argv[1]
    linhas = [normalizar(l) for l in carregar(execucao)]
    for l in linhas:
        l["estrategia_curta"] = l["tentativa_id"].split("_")[3]
    desenho = [l for l in linhas if l["condicao"] == "desenho"]
    diag = [l for l in linhas if l["condicao"] == "diagnostico"]
    ordem = sorted({l["estrategia_curta"] for l in desenho}, key=lambda e: ("P1", "P2", "P3", "P4").index(e))
    casos = sorted({l["caso_id"] for l in linhas})

    res = {"AVISO": "Calculo anterior a F7. Tentativa nao aplicada conta 0. Cadeia reconstruida por definicao.",
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
    nc = [l for l in linhas if not l.get("do_cache")]
    res["custo"] = {"chamadas_reais": len(nc), "do_cache": len(linhas) - len(nc),
                    "usd": round(sum(v(l["custo_usd"]) for l in nc), 6),
                    "tokens_entrada": sum(v(l["tokens_entrada"]) for l in nc),
                    "tokens_saida": sum(v(l["tokens_saida"]) for l in nc)}
    arq_s = RAIZ / "outputs" / "resultados_consolidados" / f"{execucao}_sessoes.json"
    if arq_s.exists():
        res["sessoes"] = [{k: s.get(k) for k in ("inicio", "fim", "duracao_s", "abortada")}
                          for s in json.loads(arq_s.read_text(encoding="utf-8"))]
    saida = RAIZ / "outputs" / "resultados_consolidados" / f"{execucao}_metricas.json"
    saida.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{execucao}: {len(casos)} casos, {len(linhas)} tentativas ({len(diag)} de diagnostico)")
    print(f"{'definicao':14} {'m':>3} {'TRV':>6} {'TRI':>6} {'TPF':>6} {'TNINI':>6} {'TAP':>6} {'TCD':>6} {'casos aceitos'}")
    for d in DEFS:
        g = res["definicoes"][d]["geral_por_tentativa"]
        pc = res["definicoes"][d]["por_caso"]
        tcd = "-" if g["TCD"] is None else f"{g['TCD']:.2f}"
        print(f"{d:14} {g['m']:>3} {g['TRV']:>6.3f} {g['TRI']:>6.3f} {g['TPF']:>6.3f} {g['TNINI']:>6.3f} "
              f"{g['TAP']:>6.3f} {tcd:>6} {len(pc['casos_aceitos'])}/{len(casos)} {pc['casos_aceitos']}"
              + (f"  [{g['indeterminadas']} indeterminada(s)]" if g["indeterminadas"] else ""))
    print("custo:", res["custo"])
    print("->", saida.relative_to(RAIZ))


if __name__ == "__main__":
    main()
