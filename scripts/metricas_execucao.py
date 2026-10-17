#!/usr/bin/env python3
"""Metricas de uma execucao nas quatro definicoes de F (protocolo, Secao 13).

Calculo anterior a F7 (src/pipeline/metrics/calculator.py ainda nao existe).
Formulas da F7 do guia: TRV = sum(R*F*M)/m, TRI = sum(R)/m, TPF = sum(F)/m,
TNINI = sum(M)/m, TAP = sum(aplicavel)/m. Tentativa nao aplicada conta 0 em R,
F e M. TCD = aceitas que derrubam >= 1 teste de D / aceitas.

Duas leituras separadas (protocolo, Secao 14):
(a) por estrategia, independente da cadeia: cada estrategia sobre todos os
    casos em que rodou. Compara estrategias (pergunta de pesquisa). Se a cadeia
    parou antes de alguma estrategia num caso, a leitura fica marcada como
    incompleta e os casos faltantes sao listados.
(b) cadeia sequencial (TCC 1): tentativas do desenho (P1, P2, ...) de um caso
    entram ate a primeira aceita NAQUELA definicao (inclusive); as posteriores
    saem, como se a cadeia tivesse parado ali. Responde "o pipeline corrige".
Condicoes de diagnostico (P1L) sao reportadas a parte.

Linhas antigas: a definicao que faltar (E01: marcador, criterio e
criterio_amplo; E02: criterio_amplo) e refeita camada por camada a partir do
arquivo de validacao. Se a escada original parou numa camada que so falhou por
testes de D daquela definicao, as camadas seguintes nao rodaram e o F refeito
fica marcado como incompleto (indeterminado). As definicoes ja gravadas sao
refeitas do mesmo modo e conferidas.

Triagem manual (protocolo, Secao 3, passo 7): casos falso_positivo,
inconclusivo etc. entram no total e tambem sao reportados a parte
(por_triagem). Linha sem o campo recebe a triagem do catalogo vigente pela
assinatura (mesma regra e arquivo).

Uso:
    python scripts/metricas_execucao.py E02
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from pipeline.validation.conjunto_d import classificar  # noqa: E402

DEFS = ("sem_separacao", "marcador", "criterio", "criterio_amplo")
ULTIMA_CAMADA = "T4"
CATALOGO = RAIZ / "outputs" / "sast_antes" / "catalogo_issues.json"
TRIAGENS = ("confirmado", "falso_positivo", "inconclusivo", "nao_triado")


def carregar(execucao: str) -> list[dict]:
    arq = RAIZ / "outputs" / "resultados_consolidados" / "execucoes.jsonl"
    linhas = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [l for l in linhas if l["execucao"] == execucao]


def refazer_escada(tiers: list[dict], d: str) -> tuple[int | None, bool]:
    """F na definicao d refeito a partir das camadas que rodaram (arquivo de
    validacao da tentativa). Retorna (F, incompleto). Camada que falhou so com
    testes de D desta definicao nao reprova; se a escada original parou nela
    antes da ultima camada, as seguintes nao rodaram e F fica indeterminado."""
    for t in tiers:
        if t["passou"]:
            continue
        testes = t.get("testes_falhos_novos") or []
        if not testes or classificar(testes)[f"f_{d}"]:
            return 0, False
    ultima = tiers[-1]
    if ultima["passou"] or ultima["tier"] == ULTIMA_CAMADA:
        return 1, False
    return None, True


def normalizar(l: dict, triagem_por_assinatura: dict[str, str]) -> dict:
    """Garante F_<def>, classificacao_<def>, testes_falhos_d_<def>, incompleto_<def>
    e triagem_manual. Definicao ausente na linha e refeita a partir do arquivo de
    validacao; as presentes sao conferidas."""
    l = dict(l)
    l.setdefault("condicao", "desenho")
    l.setdefault("triagem_manual", triagem_por_assinatura.get(l["assinatura"], "nao_triado"))
    l.setdefault("F_sem_separacao", l["F"])
    l["testes_falhos_d_sem_separacao"] = []
    aplicado = l["status_aplicacao"] == "aplicado"
    tiers = []
    if aplicado:
        tiers = json.loads((RAIZ / l["artefatos"]["validacao"]).read_text(encoding="utf-8"))["tiers"]
    c = classificar(l.get("testes_falhos_novos") or [])
    for d in DEFS:
        l[f"incompleto_{d}"] = False
        if d == "sem_separacao":
            continue
        l.setdefault(f"testes_falhos_d_{d}", c[f"d_{d}"])
        if not aplicado:
            l[f"F_{d}"] = None
            continue
        f, incompleto = refazer_escada(tiers, d)
        if f"F_{d}" in l:
            if l[f"F_{d}"] != f:
                raise SystemExit(f"{l['tentativa_id']}: F_{d} gravado={l[f'F_{d}']} refeito={f}")
            continue
        l[f"F_{d}"], l[f"incompleto_{d}"] = f, incompleto
    for d in DEFS:
        f = l[f"F_{d}"]
        if not aplicado:
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


def por_estrategia(ls: list[dict], d: str, casos: list[str]) -> dict | None:
    """Leitura (a): todas as tentativas da estrategia, sem cortar pela cadeia."""
    ind = indices(ls, d)
    if ind is None:
        return None
    rodou = {l["caso_id"] for l in ls}
    ind["casos_aceitos"] = sorted({l["caso_id"] for l in ls if l[f"classificacao_{d}"] == "aceita"})
    ind["casos_sem_tentativa"] = sorted(set(casos) - rodou)
    ind["completa"] = not ind["casos_sem_tentativa"]
    return ind


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
    triagem = {c["assinatura"]: c["triagem_manual"]
               for c in json.loads(CATALOGO.read_text(encoding="utf-8")) if c.get("triagem_manual")}
    linhas = [normalizar(l, triagem) for l in carregar(execucao)]
    for l in linhas:
        l["estrategia_curta"] = l["tentativa_id"].split("_")[3]
    desenho = [l for l in linhas if l["condicao"] == "desenho"]
    diag = [l for l in linhas if l["condicao"] == "diagnostico"]
    ordem = sorted({l["estrategia_curta"] for l in desenho}, key=lambda e: ("P1", "P2", "P3", "P4").index(e))
    casos = sorted({l["caso_id"] for l in linhas})
    triagem_caso = {l["caso_id"]: l["triagem_manual"] for l in linhas}

    res = {"AVISO": "Calculo anterior a F7. Tentativa nao aplicada conta 0. "
                    "a_por_estrategia: cada estrategia sobre todos os casos (compara estrategias). "
                    "b_cadeia: cadeia reconstruida por definicao (o pipeline corrige?).",
           "execucao": execucao, "casos": len(casos), "definicoes": {}}
    for d in DEFS:
        cad = cadeia(desenho, d, ordem)
        aceitos = sorted({l["caso_id"] for l in cad if l[f"classificacao_{d}"] == "aceita"})
        grupos = [t for t in TRIAGENS if t in triagem_caso.values()]
        res["definicoes"][d] = {
            "a_por_estrategia": {e: por_estrategia([l for l in desenho if l["estrategia_curta"] == e], d, casos)
                                 for e in ordem},
            # Os mesmos casos, separados pela triagem manual (ja incluidos no total acima).
            "a_por_estrategia_por_triagem": {
                t: {e: por_estrategia([l for l in desenho if l["estrategia_curta"] == e
                                       and l["triagem_manual"] == t], d,
                                      [c for c in casos if triagem_caso[c] == t]) for e in ordem}
                for t in grupos},
            "b_cadeia": {
                "geral_por_tentativa": indices(cad, d),
                "por_estrategia_na_cadeia": {e: indices([l for l in cad if l["estrategia_curta"] == e], d)
                                             for e in ordem},
                "por_caso": {"casos_aceitos": aceitos,
                             "TRV_caso": round(len(aceitos) / len(casos), 4) if casos else None},
                "por_caso_por_triagem": {
                    t: {"casos": (n := sum(1 for c in casos if triagem_caso[c] == t)),
                        "casos_aceitos": [c for c in aceitos if triagem_caso[c] == t],
                        "TRV_caso": round(sum(1 for c in aceitos if triagem_caso[c] == t) / n, 4)}
                    for t in grupos},
            },
            "diagnostico_P1L": indices(diag, d) if diag else None,
        }
    tabela = []
    for caso in casos:
        ls = sorted([l for l in linhas if l["caso_id"] == caso],
                    key=lambda x: (x["condicao"] != "desenho", x["estrategia_curta"]))
        tabela.append({"caso": caso, "sigla": ls[0]["sigla_vuln"], "faixa": ls[0].get("faixa_regra"),
                       "triagem_manual": ls[0]["triagem_manual"],
                       "tentativas": [{
                           "estrategia": l["estrategia_curta"], "condicao": l["condicao"],
                           "aplicacao": l["status_aplicacao"], "R": l["R"], "M": l["M"],
                           **{f"F_{d}": l[f"F_{d}"] for d in DEFS},
                           **{f"classificacao_{d}": l[f"classificacao_{d}"] for d in DEFS},
                           "tier_falha": l.get("tier_falha"),
                           "n_d_marcador": len(l["testes_falhos_d_marcador"]),
                           "n_d_criterio": len(l["testes_falhos_d_criterio"]),
                           "n_d_criterio_amplo": len(l["testes_falhos_d_criterio_amplo"]),
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

    def linha_tab(rotulo: str, g: dict, aceitos: list[str]) -> str:
        tcd = "-" if g["TCD"] is None else f"{g['TCD']:.2f}"
        return (f"{rotulo:20} {g['m']:>3} {g['TRV']:>6.3f} {g['TRI']:>6.3f} {g['TPF']:>6.3f} {g['TNINI']:>6.3f} "
                f"{g['TAP']:>6.3f} {tcd:>6} {len(aceitos)}/{len(casos)} {aceitos}"
                + (f"  [{g['indeterminadas']} indeterminada(s)]" if g["indeterminadas"] else ""))

    print(f"{execucao}: {len(casos)} casos, {len(linhas)} tentativas ({len(diag)} de diagnostico)")
    cab = f"{'':20} {'m':>3} {'TRV':>6} {'TRI':>6} {'TPF':>6} {'TNINI':>6} {'TAP':>6} {'TCD':>6} casos aceitos"
    print("\n(a) por estrategia, independente da cadeia")
    print(cab)
    for d in DEFS:
        for e, g in res["definicoes"][d]["a_por_estrategia"].items():
            print(linha_tab(f"{d}/{e}", g, g["casos_aceitos"])
                  + ("" if g["completa"] else f"  [INCOMPLETA: sem {g['casos_sem_tentativa']}]"))
    print("\n(b) cadeia sequencial")
    print(cab)
    for d in DEFS:
        b = res["definicoes"][d]["b_cadeia"]
        print(linha_tab(d, b["geral_por_tentativa"], b["por_caso"]["casos_aceitos"]))
    print("\nPor triagem manual (ja incluidos no total; criterio):")
    for t, g in res["definicoes"]["criterio"]["b_cadeia"]["por_caso_por_triagem"].items():
        a = res["definicoes"]["criterio"]["a_por_estrategia_por_triagem"][t]
        print(f"  {t:15} {g['casos']:>2} casos | cadeia: {len(g['casos_aceitos'])} aceitos {g['casos_aceitos']} | "
              + " ".join(f"{e}: {len(x['casos_aceitos'])}" for e, x in a.items()))
    print("custo:", res["custo"])
    print("->", saida.relative_to(RAIZ))


if __name__ == "__main__":
    main()
