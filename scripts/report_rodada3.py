#!/usr/bin/env python3
"""Compara a matriz da rodada 2 com a ultima rodada de regras."""
import json
from pathlib import Path

from report_rodada2 import ROOT, resumir


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
