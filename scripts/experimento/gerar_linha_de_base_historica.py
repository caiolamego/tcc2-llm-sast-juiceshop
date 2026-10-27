#!/usr/bin/env python3
"""Linha de base dos testes (decisao do grupo, 2026-10-07).

Roda T3 (suite unitaria de servidor) e T4 (testes de API) num worktree sem
alteracao e grava outputs/baseline_testes.json com o commit do alvo, a data,
a versao do Node e o nome de cada teste que falhou. O runner usa esse
arquivo: F=1 quando as falhas apos a correcao estao contidas nas daqui.

Uso:
    python scripts/experimento/gerar_linha_de_base_historica.py
"""
from __future__ import annotations

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402


import json
import subprocess
import sys
from datetime import datetime, timezone

from dotenv import dotenv_values

from pathlib import Path


from pipeline.comum.caminhos import rel  # noqa: E402
from pipeline.etapas.e06_aplicacao.worktrees import PoolWorktrees  # noqa: E402
from pipeline.etapas.e07_validacao.camadas import ARQ_LINHA_DE_BASE, ConfigValidacao, rodar_suite  # noqa: E402


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=ARQ_LINHA_DE_BASE)
    ap.add_argument("--commit")
    args = ap.parse_args()
    if args.saida.exists():
        raise SystemExit("Saída já existe; escolha --saida nova para preservar evidências")
    commit = args.commit or dotenv_values(RAIZ_REPO / ".env").get("JUICESHOP_COMMIT")
    pool = PoolWorktrees(RAIZ_REPO / "workspace", k=1, commit_esperado=commit)
    cfg = ConfigValidacao()
    node = subprocess.run(["node", "--version"], capture_output=True, text=True,
                          timeout=30).stdout.strip()

    tiers: dict[str, dict] = {}
    with pool.alugar() as wt:
        for tier, timeout_s in [("T3", cfg.timeout_t3_s), ("T4", cfg.timeout_t4_s)]:
            print(f"[{tier}] rodando em {wt.name}...")
            r = rodar_suite(tier, wt, timeout_s, linha_de_base=None)
            if r.motivo in ("timeout", "comando_nao_encontrado", "falha_sem_relatorio"):
                raise SystemExit(f"{tier} nao produziu relatorio confiavel ({r.motivo}):\n{r.saida[-1500:]}")
            tiers[tier] = {
                "comando": r.comando,
                "codigo_saida": r.codigo_saida,
                "duracao_s": r.duracao_s,
                "testes_falhos": r.testes_falhos,
            }
            print(f"  -> codigo {r.codigo_saida}, {len(r.testes_falhos)} teste(s) falho(s) em {r.duracao_s}s")
            for t in r.testes_falhos:
                print(f"     - {t}")
        worktree = wt.name

    dados = {
        "commit_alvo": commit,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "node": node,
        "worktree": worktree,
        "tiers": tiers,
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nLinha de base gravada em {rel(args.saida)}")


if __name__ == "__main__":
    main()
