#!/usr/bin/env python3
"""Cruza outputs/sast_antes/catalogo_issues.json (F3.4) com os marcadores
'vuln-code-snippet' do proprio Juice Shop. Atualiza o catalogo IN-PLACE,
preenchendo 'marcador_juiceshop' nos findings elegiveis cuja faixa de
linhas cai dentro de um bloco marcado (ground truth parcial -- nem toda
vulnerabilidade real do Juice Shop tem marcador, mas todo marcador aponta
para uma vulnerabilidade intencional conhecida).

Uso:
    python scripts/experiment/mark_juiceshop_challenges.py --worktree workspace/wt-1
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
import re
from pathlib import Path


CATALOGO = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_issues.json"

PADRAO_MARCADOR = re.compile(r"vuln-code-snippet\s+(start|end)\s+(.+?)\s*(?:-->|\*/)?\s*$")
EXTENSOES_FONTE = {".ts", ".js", ".html"}
# Mesmos diretorios excluidos do SAST (D1) -- um marcador dentro deles
# nunca poderia bater com um finding do catalogo de qualquer forma, ja
# que o scan nunca olhou esses caminhos.
EXCLUIR_PARTES = {"node_modules", "build", "dist", "coverage", ".git", "logs", "codefixes", "test"}


def arquivos_fonte(worktree: Path):
    for caminho in worktree.rglob("*"):
        if not caminho.is_file() or caminho.suffix not in EXTENSOES_FONTE:
            continue
        if set(caminho.relative_to(worktree).parts) & EXCLUIR_PARTES:
            continue
        yield caminho


def extrair_blocos(worktree: Path) -> list[dict]:
    """Retorna [{arquivo, desafio, linha_inicio, linha_fim}, ...]."""
    blocos: list[dict] = []
    for caminho in arquivos_fonte(worktree):
        try:
            linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        abertos: dict[str, int] = {}
        rel = str(caminho.relative_to(worktree))
        for i, linha in enumerate(linhas, start=1):
            m = PADRAO_MARCADOR.search(linha)
            if not m:
                continue
            acao, nomes_str = m.group(1), m.group(2)
            for nome in (n.strip() for n in re.split(r"[\s,]+", nomes_str) if n.strip()):
                if acao == "start":
                    abertos[nome] = i
                else:
                    inicio = abertos.pop(nome, None)
                    if inicio is not None:
                        blocos.append({"arquivo": rel, "desafio": nome,
                                        "linha_inicio": inicio, "linha_fim": i})
    return blocos


def sobrepoe(a_ini: int, a_fim: int, b_ini: int, b_fim: int) -> bool:
    return a_ini <= b_fim and b_ini <= a_fim


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", default="workspace/wt-1")
    args = ap.parse_args()
    worktree = (RAIZ_REPO / args.worktree).resolve()

    if not CATALOGO.exists():
        raise SystemExit(f"Catalogo nao encontrado: {CATALOGO}. Rode F3.4 primeiro.")

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    blocos = extrair_blocos(worktree)
    print(f"Blocos vuln-code-snippet encontrados: {len(blocos)}")

    blocos_por_arquivo: dict[str, list[dict]] = {}
    for b in blocos:
        blocos_por_arquivo.setdefault(b["arquivo"], []).append(b)

    coincidencias = 0
    for entrada in catalogo:
        if not entrada["elegivel"]:
            continue
        casados = [
            b["desafio"] for b in blocos_por_arquivo.get(entrada["arquivo"], [])
            if sobrepoe(entrada["linha_inicio"], entrada["linha_fim"], b["linha_inicio"], b["linha_fim"])
        ]
        if casados:
            entrada["marcador_juiceshop"] = ", ".join(sorted(set(casados)))
            coincidencias += 1

    elegiveis = [e for e in catalogo if e["elegivel"]]
    print(f"Findings elegiveis com marcador: {coincidencias} de {len(elegiveis)}")

    CATALOGO.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Catalogo atualizado em {CATALOGO}")


if __name__ == "__main__":
    main()