#!/usr/bin/env python3
"""Compara a rodada 7 preservando integralmente a revisao SSTI da rodada 6."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402

import json

from scripts.relatorios.relatorio_rodada2 import ROOT, resumir

OLD = ROOT / "outputs/auditoria_sast/rodada6/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada7/matriz_desafios.json"
OUT = ROOT / "outputs/auditoria_sast/rodada7/resumo.json"
PERFIS = {"default", "custom-rules", "rodada2", "rodada3", "rodada4", "rodada5", "rodada6", "rodada7"}


def comparar(antes: dict, depois: dict) -> dict:
    for campo in ("revisoes_associacoes", "revisoes_sha256"):
        if antes.get(campo) != depois.get(campo):
            raise ValueError("Historico da revisao SSTI alterado")
    return resumir(antes, depois, novo_scan="rodada7", perfis=PERFIS)


def main() -> None:
    resumo = comparar(json.loads(OLD.read_text(encoding="utf-8")),
                      json.loads(NEW.read_text(encoding="utf-8")))
    OUT.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
