#!/usr/bin/env python3
"""Compara a matriz da rodada 2 com a ultima rodada de regras."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402

import json
from pathlib import Path

from scripts.relatorios.relatorio_rodada2 import ROOT, resumir


OLD = ROOT / "outputs/auditoria_sast/rodada2/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada3/matriz_desafios.json"
OUT = ROOT / "outputs/auditoria_sast/rodada3/resumo.json"
PERFIS = {"default", "custom-rules", "rodada2", "rodada3"}


def main() -> None:
    antes = json.loads(OLD.read_text(encoding="utf-8"))
    depois = json.loads(NEW.read_text(encoding="utf-8"))
    resumo = resumir(antes, depois, novo_scan="rodada3", perfis=PERFIS)
    OUT.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
