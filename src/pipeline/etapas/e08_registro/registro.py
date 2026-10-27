"""Registro incremental de tentativas em execucoes.jsonl (F6, append + flush).

Toda linha leva commit_alvo (decisao do grupo, 2026-10-07): o valor vem do
.env e e conferido contra o HEAD do worktree usado na tentativa. Linha sem
commit conferido nao e gravada.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

from dotenv import dotenv_values

from pipeline.comum.caminhos import RAIZ_REPO

ARQ_EXECUCOES = RAIZ_REPO / "outputs" / "resultados_consolidados" / "execucoes.jsonl"
_LOCK = threading.Lock()  # varios workers gravando no mesmo arquivo


def commit_alvo(wt: Path, commit_esperado: str | None = None) -> str:
    esperado = commit_esperado or dotenv_values(RAIZ_REPO / ".env").get("JUICESHOP_COMMIT")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True,
                          text=True, check=True, timeout=30).stdout.strip()
    if not esperado or head != esperado:
        raise RuntimeError(f"{Path(wt).name} em {head}, .env fixa {esperado}: tentativa nao registrada")
    return head


def registrar_execucao(linha: dict, wt: Path, arquivo: Path = ARQ_EXECUCOES, commit_esperado: str | None = None) -> None:
    """Acrescenta uma linha (uma tentativa) e forca a escrita em disco."""
    registro = {**linha, "commit_alvo": commit_alvo(wt, commit_esperado)}
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, arquivo.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def ler_execucoes(arquivo: Path = ARQ_EXECUCOES) -> list[dict]:
    """Linhas ja gravadas (para retomada). Linha final truncada por queda do
    processo e ignorada."""
    if not arquivo.exists():
        return []
    linhas = []
    for bruta in arquivo.read_text(encoding="utf-8").splitlines():
        try:
            linhas.append(json.loads(bruta))
        except json.JSONDecodeError:
            continue
    return linhas
