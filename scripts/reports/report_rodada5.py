#!/usr/bin/env python3
"""Compara a rodada 4 com a auditoria de consultas por ID e avaliacao B2B."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import json

from scripts.reports.report_rodada2 import ROOT, resumir

OLD = ROOT / "outputs/auditoria_sast/rodada4/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada5/matriz_desafios.json"
OUT = ROOT / "outputs/auditoria_sast/rodada5/resumo.json"
PERFIS = {"default", "custom-rules", "rodada2", "rodada3", "rodada4", "rodada5"}


def main() -> None:
    antes = json.loads(OLD.read_text(encoding="utf-8"))
    depois = json.loads(NEW.read_text(encoding="utf-8"))
    resumo = resumir(antes, depois, novo_scan="rodada5", perfis=PERFIS)
    OUT.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
