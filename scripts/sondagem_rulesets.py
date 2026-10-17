#!/usr/bin/env python3
"""Sondagem de varredura SAST, sem LLM e sem tocar no catalogo oficial.

Roda o Semgrep no worktree limpo com os rulesets pedidos (ou so analisa um JSON
ja gerado, com --analisar), aplica o protocolo de filtragem da Secao 3 passo a
passo e compara com um baseline de referencia (--referencia; padrao: o
baseline de setembro, outputs/sast_antes/baseline_raw_v1.json). Usada para
medir o efeito de ampliar os rulesets e de rodar com login (caderno,
2026-10-13). Nada aqui altera outputs/sast_antes/.

Saida em <--saida>/: baseline_raw.json (se varreu) e resumo.json. Recusa
sobrescrever uma pasta que ja tenha resumo.json.

Uso:
    python scripts/sondagem_rulesets.py --rulesets p/javascript,... --rotulo ... --saida outputs/sondagens/x
    python scripts/sondagem_rulesets.py --analisar outputs/sast_antes/baseline_raw_v1.json --rotulo ... --saida ...
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_REPO / "src"))
sys.path.insert(0, str(RAIZ_REPO / "scripts"))
from build_issue_catalog import carregar_yaml, extrair_cwe_numero, extrair_owasp_2021  # noqa: E402
from pipeline.caminhos import rel  # noqa: E402
from pipeline.sast.filtro import SEVERIDADES_ACEITAS  # noqa: E402
from pipeline.sast.semgrep_client import (RULESETS, SENTINELA_SEM_LOGIN, carregar_resultados,  # noqa: E402
                                          executar, ler_exclusoes)

BASELINE_V1 = RAIZ_REPO / "outputs" / "sast_antes" / "baseline_raw_v1.json"
MAPA_CWE = RAIZ_REPO / "config" / "mapa_cwe_vuln.yaml"
MAPA_OWASP = RAIZ_REPO / "config" / "mapa_owasp.yaml"


def autenticado() -> bool:
    """Ha token do Semgrep (settings.yml ou variavel)? Nao imprime o token."""
    if os.environ.get("SEMGREP_APP_TOKEN"):
        return True
    cfg = Path.home() / ".semgrep" / "settings.yml"
    return cfg.exists() and "api_token" in cfg.read_text(encoding="utf-8")


def campos_login(raw: dict) -> dict:
    """Quantos resultados trazem fingerprint/lines preenchidos (e nao a sentinela)."""
    res = raw.get("results", [])

    def preenchido(campo: str) -> int:
        return sum(1 for r in res
                   if (v := r.get("extra", {}).get(campo)) and v.strip() != SENTINELA_SEM_LOGIN)
    return {"resultados": len(res), "fingerprint_preenchido": preenchido("fingerprint"),
            "lines_preenchido": preenchido("lines"),
            "exemplo_fingerprint": next((v for r in res if (v := r.get("extra", {}).get("fingerprint"))
                                         and v.strip() != SENTINELA_SEM_LOGIN), None)}


def funil(findings, mapa_cwe: dict, mapa_owasp: dict) -> dict:
    """Secao 3, passos 2-5, nesta ordem, com a contagem depois de cada passo."""
    passos = {"0_brutos_apos_exclusao_de_caminhos": len(findings)}
    f2 = [f for f in findings if f.category == "security"]
    passos["2_categoria_security"] = len(f2)
    f3 = [f for f in f2 if f.severity in SEVERIDADES_ACEITAS]
    passos["3_severidade"] = len(f3)
    f4 = [f for f in f3 if f.cwe]
    passos["4_com_cwe"] = len(f4)
    vistos, f5 = set(), []
    for f in f4:
        if (f.check_id, f.path) not in vistos:
            vistos.add((f.check_id, f.path))
            f5.append(f)
    passos["5_dedup_check_id_path"] = len(f5)

    cwes = [extrair_cwe_numero(f.cwe) for f in f5]
    siglas = Counter(mapa_cwe.get(c, "OUTRO") for c in cwes)
    owasp = Counter((mapa_owasp.get(o) if (o := extrair_owasp_2021(f.owasp)) else None) or "sem_owasp"
                    for f in f5)
    novas = Counter(c for c in cwes if c not in mapa_cwe)
    return {
        "passos": passos,
        "elegiveis": len(f5),
        "por_sigla": dict(siglas.most_common()),
        "por_owasp_2025": dict(sorted(owasp.items())),
        "cwes_fora_do_mapa": {c: {"elegiveis": n,
                                  "exemplos": sorted({f"{f.check_id.split('.')[-1]} @ {f.path}"
                                                      for f in f5 if extrair_cwe_numero(f.cwe) == c})[:5]}
                              for c, n in novas.most_common()},
        "por_regra": dict(Counter(f.check_id for f in f5).most_common()),
        "excluidos_por_passo": {
            "2_categoria": dict(Counter(f.category or "(vazia)" for f in findings if f.category != "security")),
            "3_severidade": dict(Counter(f.severity for f in f2 if f.severity not in SEVERIDADES_ACEITAS)),
            "4_sem_cwe": len(f3) - len(f4),
            "5_duplicatas": len(f4) - len(f5),
        },
        "elegiveis_lista": sorted(f"{f.check_id} @ {f.path}:{f.start_line}" for f in f5),
        "_chaves": {(f.check_id, f.path) for f in f5},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rulesets", default=",".join(RULESETS))
    ap.add_argument("--exclusoes", default="config/semgrepignore",
                    help="arquivo de exclusoes de caminho (padrao: o vigente)")
    ap.add_argument("--worktree", default="workspace/wt-1")
    ap.add_argument("--analisar", default=None, help="JSON bruto ja gerado (nao varre)")
    ap.add_argument("--referencia", default=str(BASELINE_V1.relative_to(RAIZ_REPO)))
    ap.add_argument("--rotulo", required=True)
    ap.add_argument("--saida", required=True)
    args = ap.parse_args()

    wt = (RAIZ_REPO / args.worktree).resolve()
    saida = (RAIZ_REPO / args.saida).resolve()
    referencia = (RAIZ_REPO / args.referencia).resolve()
    if (saida / "resumo.json").exists():
        raise SystemExit(f"{rel(saida)} ja tem resumo.json; use outra --saida")
    sujo = subprocess.run(["git", "status", "--porcelain"], cwd=wt, capture_output=True, text=True).stdout
    if sujo.strip():
        raise SystemExit(f"{wt.name} tem alteracoes; restaure antes de varrer")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True).stdout.strip()

    rulesets = [r.strip() for r in args.rulesets.split(",") if r.strip()]
    exclusoes = ler_exclusoes(RAIZ_REPO / args.exclusoes)
    duracao = None
    if args.analisar:
        arq_raw = (RAIZ_REPO / args.analisar).resolve()
        rulesets = exclusoes = None
    else:
        saida.mkdir(parents=True, exist_ok=True)
        arq_raw = saida / "baseline_raw.json"
        inicio = time.monotonic()
        executar(wt, rulesets, saida_bruta=arq_raw, exclusoes=exclusoes)
        duracao = round(time.monotonic() - inicio, 1)

    raw = json.loads(arq_raw.read_text(encoding="utf-8"))
    mapa_cwe, mapa_owasp = carregar_yaml(MAPA_CWE), carregar_yaml(MAPA_OWASP)
    atual = funil(carregar_resultados(arq_raw, wt), mapa_cwe, mapa_owasp)
    oficial = funil(carregar_resultados(referencia, wt), mapa_cwe, mapa_owasp)
    trip = lambda d: {(r["check_id"], r["path"], r["start"]["line"]) for r in d.get("results", [])}  # noqa: E731
    raw_of = json.loads(referencia.read_text(encoding="utf-8"))
    ka, ko = atual.pop("_chaves"), oficial.pop("_chaves")

    resumo = {
        "rotulo": args.rotulo,
        "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_alvo": commit,
        "semgrep_versao": raw.get("version"),
        "autenticado": autenticado() if not args.analisar else None,
        "rulesets": rulesets,
        "exclusoes_caminho": exclusoes,
        "duracao_s": duracao,
        "json_bruto": rel(arq_raw),
        "erros_semgrep": len(raw.get("errors", [])),
        "arquivos_varridos": len(raw.get("paths", {}).get("scanned", [])),
        "campos_login": campos_login(raw),
        "funil": atual,
        "comparacao_referencia": {
            "referencia": rel(referencia),
            "brutos": {"referencia": len(raw_of.get("results", [])), "esta": len(raw.get("results", []))},
            "triplos_regra_arquivo_linha_so_na_referencia": sorted(map(list, trip(raw_of) - trip(raw))),
            "triplos_so_nesta": len(trip(raw) - trip(raw_of)),
            "regras_disparadas": {"referencia": len({r["check_id"] for r in raw_of["results"]}),
                                  "esta": len({r["check_id"] for r in raw["results"]})},
            "regras_so_nesta": sorted({r["check_id"] for r in raw["results"]}
                                      - {r["check_id"] for r in raw_of["results"]}),
            "regras_so_na_referencia": sorted({r["check_id"] for r in raw_of["results"]}
                                              - {r["check_id"] for r in raw["results"]}),
            "elegiveis": {"referencia": oficial["elegiveis"], "esta": atual["elegiveis"]},
            "elegiveis_da_referencia_ausentes_nesta": sorted(f"{c} @ {p}" for c, p in ko - ka),
            "elegiveis_novos": len(ka - ko),
        },
    }
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    c = resumo["comparacao_referencia"]
    print(f"{args.rotulo}: semgrep {resumo['semgrep_versao']}, autenticado={resumo['autenticado']}, "
          f"{resumo['duracao_s']}s, erros={resumo['erros_semgrep']}")
    print("funil:", atual["passos"])
    print("por sigla:", atual["por_sigla"])
    print("por OWASP 2025:", atual["por_owasp_2025"])
    print("CWEs fora do mapa:", {k: v["elegiveis"] for k, v in atual["cwes_fora_do_mapa"].items()})
    print("campos de login:", resumo["campos_login"])
    print(f"vs referencia: brutos {c['brutos']}, elegiveis {c['elegiveis']}, "
          f"ausentes {len(c['elegiveis_da_referencia_ausentes_nesta'])}, novos {c['elegiveis_novos']}")
    print("->", rel(saida / "resumo.json"))


if __name__ == "__main__":
    main()
