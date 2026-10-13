#!/usr/bin/env python3
"""Compara scans exploratorios do Semgrep com o baseline congelado.

Uso:
    python3 scripts/audit/audit_semgrep_coverage.py \
        outputs/sast_antes/baseline_raw.json /tmp/security-audit.json

Nao modifica o catalogo. A saida mostra ocorrencias e pares regra/arquivo
separadamente, pois a deduplicacao atual pode ocultar locais distintos.
"""
from __future__ import annotations

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402


import argparse
import json
from pathlib import Path


def carregar(caminho: Path) -> dict:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados.get("results"), list):
        raise ValueError(f"{caminho}: JSON sem lista 'results'")
    return dados


def local(achado: dict) -> tuple[str, int]:
    return achado["path"], achado["start"]["line"]


def regra_arquivo(achado: dict) -> tuple[str, str]:
    return achado["check_id"], achado["path"]


def resumo(nome: str, dados: dict, baseline: dict | None = None) -> None:
    resultados = dados["results"]
    pares = {regra_arquivo(a) for a in resultados}
    locais = {local(a) for a in resultados}
    avisos = dados.get("errors", [])
    print(f"\n{nome}: {len(resultados)} ocorrencias, {len(pares)} pares regra/arquivo, "
          f"{len(locais)} locais, {len(avisos)} avisos")
    if baseline is None:
        return

    pares_base = {regra_arquivo(a) for a in baseline["results"]}
    locais_base = {local(a) for a in baseline["results"]}
    novos_pares = [a for a in resultados if regra_arquivo(a) not in pares_base]
    novos_locais = [a for a in resultados if local(a) not in locais_base]
    print(f"  Novos: {len({regra_arquivo(a) for a in novos_pares})} pares regra/arquivo; "
          f"{len({local(a) for a in novos_locais})} locais")
    for a in sorted(novos_locais, key=lambda x: (x["path"], x["start"]["line"], x["check_id"])):
        meta = a.get("extra", {}).get("metadata", {})
        cwe = meta.get("cwe") or []
        cwe = cwe[0].split(":", 1)[0] if cwe else "sem CWE"
        print(f"  {a['path']}:{a['start']['line']}  {cwe}  {a['check_id']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidatos", type=Path, nargs="+")
    args = parser.parse_args()
    baseline = carregar(args.baseline)
    resumo(f"Baseline ({args.baseline})", baseline)
    for caminho in args.candidatos:
        resumo(str(caminho), carregar(caminho), baseline)


if __name__ == "__main__":
    main()
