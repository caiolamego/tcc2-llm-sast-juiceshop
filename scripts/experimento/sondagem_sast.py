#!/usr/bin/env python3
"""Sondagem do oraculo R, sem LLM: aplica um patch num worktree alugado,
varre o arquivo do caso com os rulesets do protocolo antes (estado limpo) e
depois, e diz se o alerta original persiste. Opcionalmente roda a validacao.

Os patches de outputs/sondagens/ marcados como ESCRITO_A_MAO NAO sao saida da
LLM e nao entram em nenhuma metrica do experimento.

Uso:
    python scripts/experimento/sondagem_sast.py --caso JS003 --patch <arquivo.diff> --rotulo <nome> [--validar]
"""
from __future__ import annotations

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402


import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values


from pipeline.comum.caminhos import rel  # noqa: E402
from pipeline.etapas.e01_analise_sast.semgrep import RULESETS, assinatura, executar  # noqa: E402
from pipeline.etapas.e06_aplicacao.worktrees import PoolWorktrees  # noqa: E402
from pipeline.etapas.e07_validacao.camadas import validar  # noqa: E402

CATALOGO = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_issues.json"
DIR_SAIDA = RAIZ_REPO / "outputs" / "sondagens"


def resumo_findings(findings) -> list[dict]:
    return [{"check_id": f.check_id, "linha": f.start_line, "assinatura": assinatura(f)}
            for f in findings]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso", required=True)
    ap.add_argument("--patch", required=True, help="diff aplicavel com 'git apply'")
    ap.add_argument("--rotulo", required=True, help="nome do artefato em outputs/sondagens/")
    ap.add_argument("--origem", required=True, choices=["LLM_ARQUIVADA", "ESCRITO_A_MAO"])
    ap.add_argument("--validar", action="store_true")
    ap.add_argument('--catalogo', type=Path, default=CATALOGO)
    ap.add_argument('--perfil-sast', type=Path)
    ap.add_argument('--semgrep-bin', default='semgrep')
    ap.add_argument('--saida', type=Path)
    ap.add_argument('--baseline-testes', type=Path, default=RAIZ_REPO/'outputs/baseline_testes.json')
    from pipeline.etapas.e07_validacao.politicas import argumentos, opcoes, alterada
    argumentos(ap)
    args = ap.parse_args()

    from pipeline.etapas.e02_catalogo.catalogo import carregar
    catalogo = carregar(args.catalogo)
    if not catalogo.ampliado and alterada(args):
        raise SystemExit("Otimizações requerem catálogo ampliado")
    if catalogo.ampliado:
        from pipeline.orquestracao.preflight import sondar
        sondar(args, catalogo)
        return
    issue = next(i for i in catalogo.casos if i["caso_id"] == args.caso)
    patch = Path(args.patch).resolve()
    alvo_sig = issue["assinatura"]
    env = dotenv_values(RAIZ_REPO / ".env")
    pool = PoolWorktrees(RAIZ_REPO / "workspace", k=1, commit_esperado=env.get("JUICESHOP_COMMIT"))

    with pool.alugar() as wt:
        antes = executar(wt, RULESETS, caminhos=[issue["arquivo"]], semgrep_bin=args.semgrep_bin)
        subprocess.run(["git", "apply", str(patch)], cwd=wt, check=True, timeout=60)
        diff = subprocess.run(["git", "diff"], cwd=wt, capture_output=True, text=True,
                              timeout=60).stdout
        depois = executar(wt, RULESETS, caminhos=[issue["arquivo"]], semgrep_bin=args.semgrep_bin)
        v = validar(wt, [issue["arquivo"]]) if args.validar else None

    sig_antes = {assinatura(f) for f in antes}
    sig_depois = {assinatura(f) for f in depois}
    resultado = {
        "AVISO": ("Correcao ESCRITA A MAO para sondar o oraculo R; nao e saida da LLM e nao "
                  "entra em nenhuma metrica." if args.origem == "ESCRITO_A_MAO"
                  else "Patch de tentativa exploratoria da LLM, reaplicado so para sondar o R."),
        "origem_patch": args.origem,
        "caso": args.caso, "check_id": issue["check_id"], "arquivo": issue["arquivo"],
        "patch": rel(patch), "diff": diff,
        "commit_alvo": env.get("JUICESHOP_COMMIT"),
        "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rulesets": RULESETS,
        "alerta_no_antes": alvo_sig in sig_antes,
        "alerta_persiste": alvo_sig in sig_depois,
        "R": int(alvo_sig in sig_antes and alvo_sig not in sig_depois),
        "alertas_novos": sorted(sig_depois - sig_antes),
        "findings_antes": resumo_findings(antes),
        "findings_depois": resumo_findings(depois),
        "validacao": None if v is None else {
            "passou": v.passou, "tier_falha": v.tier_falha,
            "testes_falhos_novos": v.testes_falhos_novos,
            "testes_falhos_intermitentes": v.testes_falhos_intermitentes,
            "reexecucoes": v.reexecucoes,
            "tiers": {t.tier: {"passou": t.passou, "motivo": t.motivo} for t in v.tiers},
        },
    }
    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    arq = DIR_SAIDA / f"{args.rotulo}.json"
    arq.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[{args.rotulo}] {args.caso} {issue['arquivo']} ({args.origem})")
    print(f"  alerta antes: {resultado['alerta_no_antes']} | persiste depois: {resultado['alerta_persiste']} "
          f"| R={resultado['R']} | novos: {len(resultado['alertas_novos'])}")
    if v is not None:
        print(f"  validacao: passou={v.passou} tier_falha={v.tier_falha} novos={v.testes_falhos_novos}")
    print(f"  -> {rel(arq)}")


if __name__ == "__main__":
    main()
