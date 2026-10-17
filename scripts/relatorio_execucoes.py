#!/usr/bin/env python3
"""Resumo objetivo das execucoes em markdown: issues, correcoes, prompts,
custo e tempo. Le so arquivos ja gerados (execucoes.jsonl, <EXECUCAO>_sessoes.json,
<EXECUCAO>_metricas.json, catalogos e sondagens); nao chama LLM nem Semgrep.

Uso:
    python scripts/relatorio_execucoes.py E01 E02 E03 > docs/relatorio_execucoes.md
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RC = RAIZ / "outputs" / "resultados_consolidados"
SA = RAIZ / "outputs" / "sast_antes"
DEFS = ("sem_separacao", "marcador", "criterio", "criterio_amplo")
NOME_DEF = {"sem_separacao": "sem separação", "marcador": "d_marcador",
            "criterio": "d_criterio", "criterio_amplo": "d_criterio_amplo"}
CATALOGO_DA_EXECUCAO = {"E01": "v1", "E02": "v1"}  # demais: v2


def ler_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def fmt_s(seg: float) -> str:
    m, s = divmod(round(seg), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def usd(x: float) -> str:
    return f"US$ {x:.4f}".replace(".", ",")


def num(x: float, casas: int = 3) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def secao_issues() -> list[str]:
    out = ["## Issues (alertas do Semgrep)", ""]
    linhas = [("Catálogo", "Rulesets", "Brutos", "Elegíveis", "Locais distintos", "Com `vuln-code-snippet`")]
    for rot, cat, meta in (("v1 (E01, E02)", "catalogo_issues_v1.json", "catalogo_meta_v1.json"),
                           ("v2 (E03)", "catalogo_issues.json", "catalogo_meta.json")):
        c, m = ler_json(SA / cat), ler_json(SA / meta)
        e = [x for x in c if x["elegivel"]]
        linhas.append((rot, str(len(m.get("rulesets", [None] * 5))), str(m["findings_brutos"]), str(len(e)),
                       str(len({(x["arquivo"], x["linha_inicio"]) for x in e})),
                       str(sum(1 for x in e if x.get("marcador_juiceshop")))))
    out += tabela(linhas)
    c = [x for x in ler_json(SA / "catalogo_issues.json") if x["elegivel"]]
    tri = Counter(x["triagem_manual"] for x in c)
    out += ["", f"- Triagem manual do v2: {tri['confirmado']} confirmados, {tri['falso_positivo']} falsos positivos, "
            f"{tri['inconclusivo']} inconclusivo(s), {tri['nao_triado']} não triados (nenhum é excluído).",
            "- Siglas do v2: " + ", ".join(f"{k} {v}" for k, v in Counter(x["sigla_vuln"] for x in c).most_common()) + ".",
            "- OWASP 2025 do v2: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(x["owasp_2025"] for x in c).items())) + "."]
    sond = RAIZ / "outputs" / "sondagens" / "semgrep_2026-10-16"
    if sond.exists():
        r5, r11 = ler_json(sond / "anonimo_5rulesets" / "resumo.json"), ler_json(sond / "anonimo_11rulesets" / "resumo.json")
        out.append(f"- Sondagem, exclusões antigas: 5 rulesets {r5['funil']['passos']['0_brutos_apos_exclusao_de_caminhos']} brutos / "
                   f"{r5['funil']['elegiveis']} elegíveis; 11 rulesets {r11['funil']['passos']['0_brutos_apos_exclusao_de_caminhos']} / "
                   f"{r11['funil']['elegiveis']}. Com login (13/10, não adotado): 37 brutos / 29 elegíveis.")
    return out + [""]


def tabela(linhas: list[tuple]) -> list[str]:
    cab, *corpo = linhas
    return (["| " + " | ".join(cab) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(cab))) + "|"]
            + ["| " + " | ".join(l) + " |" for l in corpo])


def main() -> None:
    execucoes = sys.argv[1:]
    todas = [json.loads(l) for l in (RC / "execucoes.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    out = [f"# Resumo das execuções ({', '.join(execucoes)})", "",
           f"Gerado em {datetime.now().strftime('%Y-%m-%d')} por `scripts/relatorio_execucoes.py`, só a partir dos arquivos em `outputs/`. "
           "Modelo `gpt-4.1-mini`, Semgrep 1.177.0 sem login, Juice Shop v20.1.1 (`f915bdd`).", ""]
    out += secao_issues()

    # Prompts, custo e tempo
    out += ["## Prompts, chamadas e custo", ""]
    lin = [("Execução", "Catálogo", "Casos", "Tentativas", "Por estratégia", "Chamadas pagas", "Do cache", "Tokens (entrada + saída)", "Custo")]
    tempo = [("Execução", "Duração da sessão", "Tentativa aplicada: média", "LLM", "SAST depois", "Validação")]
    for e in execucoes:
        ls = [l for l in todas if l["execucao"] == e]
        pagas = [l for l in ls if not l.get("do_cache")]
        por = Counter(l["tentativa_id"].split("_")[3] for l in ls)
        lin.append((e, CATALOGO_DA_EXECUCAO.get(e, "v2"), str(len({l["caso_id"] for l in ls})), str(len(ls)),
                    ", ".join(f"{k} {v}" for k, v in sorted(por.items())), str(len(pagas)), str(len(ls) - len(pagas)),
                    f"{sum(l['tokens_entrada'] or 0 for l in pagas):,} + {sum(l['tokens_saida'] or 0 for l in pagas):,}".replace(",", "."),
                    usd(sum(l["custo_usd"] or 0 for l in pagas))))
        apl = [l for l in ls if l["status_aplicacao"] == "aplicado"]
        sess = ler_json(RC / f"{e}_sessoes.json")
        dur = sum(s.get("duracao_s") or 0 for s in sess)
        media = lambda k: st.mean([(l[k] or 0) for l in apl]) if apl else 0  # noqa: E731
        tot = st.mean([(l["duracao_llm_s"] or 0) + (l["duracao_sast_s"] or 0) + (l["duracao_validacao_s"] or 0)
                       for l in apl]) if apl else 0
        tempo.append((e, f"{fmt_s(dur)} ({len(sess)} sessão(ões), K = {sess[-1].get('k')})", fmt_s(tot),
                      fmt_s(media("duracao_llm_s")), fmt_s(media("duracao_sast_s")), fmt_s(media("duracao_validacao_s"))))
    out += tabela(lin) + ["", "Chamada do cache: prompt idêntico a uma chamada anterior; não é cobrada de novo (D8).", "",
                          "## Tempo", ""] + tabela(tempo) + [
        "", "A duração da sessão é o tempo de processamento (depois da checagem de ambiente) com K cópias em paralelo; "
        "os tempos por tentativa somam as camadas de uma tentativa aplicada.", ""]

    # Correcoes
    out += ["## Correções aceitas (R = F = M = 1)", "",
            "Leitura (a): cada estratégia sobre todos os casos. Leitura (b): cadeia P1 → P2 do TCC 1, por caso. "
            "Os números são casos aceitos sobre o total de casos; P1L é diagnóstico, fora da cadeia.", ""]
    for e in execucoes:
        m = ler_json(RC / f"{e}_metricas.json")
        ordem = list(m["definicoes"]["criterio"]["a_por_estrategia"])
        cab = ("Definição de F",) + tuple(f"{x} (a)" for x in ordem) + ("Cadeia (b)", "P1L", "TRV da cadeia")
        corpo = []
        for d in DEFS:
            dd = m["definicoes"][d]
            a = [dd["a_por_estrategia"][x] for x in ordem]
            b = dd["b_cadeia"]
            p1l = dd["diagnostico_P1L"]
            corpo.append((NOME_DEF[d], *[f"{len(x['casos_aceitos'])}/{m['casos']}" for x in a],
                          f"{len(b['por_caso']['casos_aceitos'])}/{m['casos']}",
                          f"{p1l['aceitas']}/{p1l['m']}" if p1l else "-",
                          num(b["geral_por_tentativa"]["TRV"])))
        out += [f"### {e}", ""] + tabela([cab] + corpo)
        crit = m["definicoes"]["criterio"]
        aceitos = crit["b_cadeia"]["por_caso"]["casos_aceitos"]
        out += ["", f"- Casos aceitos (`d_criterio`, cadeia): {', '.join(aceitos) if aceitos else 'nenhum'}."]
        tri = crit["b_cadeia"].get("por_caso_por_triagem", {})
        if tri:
            out.append("- Por triagem manual (`d_criterio`, cadeia): " + "; ".join(
                f"{k} {len(v['casos_aceitos'])}/{v['casos']}" for k, v in tri.items()) + ".")
        ls = [l for l in todas if l["execucao"] == e]
        nao_apl = Counter(l["status_aplicacao"] for l in ls if l["status_aplicacao"] != "aplicado")
        motivos = Counter((l.get("classificacao_criterio") or l["classificacao_final"]).split(":")[-1]
                          for l in ls if l["status_aplicacao"] == "aplicado" and l["classificacao_final"] != "aceita")
        out.append(f"- Não aplicadas: {sum(nao_apl.values())} ({', '.join(f'{k} {v}' for k, v in nao_apl.items()) or '-'}). "
                   f"Rejeitadas (`d_criterio`): " + ", ".join(f"{k} {v}" for k, v in motivos.most_common()) + ".")
        out.append("")
    print("\n".join(out).rstrip() + "\n")


if __name__ == "__main__":
    main()
