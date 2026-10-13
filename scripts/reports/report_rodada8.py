#!/usr/bin/env python3
"""Rodada 8 replanejada: quatro candidatos, sem iniciar rodadas posteriores."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import json
from scripts.reports.report_rodada2 import ROOT, resumir

OLD = ROOT / "outputs/auditoria_sast/rodada7/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada8/matriz_desafios.json"
OUT = ROOT / "outputs/auditoria_sast/rodada8/resumo.json"
PERFIS = {"default", "custom-rules", *(f"rodada{i}" for i in range(2, 9))}
ALVOS = {"dataExportChallenge", "negativeOrderChallenge", "registerAdminChallenge", "forgedFeedbackChallenge"}


def comparar(antes, depois):
    for campo in ("revisoes_associacoes", "revisoes_sha256"):
        if antes.get(campo) != depois.get(campo):
            raise ValueError("Historico SSTI alterado")
    resumo = resumir(antes, depois, novo_scan="rodada8", perfis=PERFIS)
    resumo["candidatos_rodada"] = sorted(ALVOS)
    resumo["candidatos_incluidos"] = sorted(ALVOS & set(resumo["novos_desafios_confirmados"]))
    resumo["nota_escopo"] = "Pedido atual limitado aos quatro candidatos na rodada 8. Nao iniciar rodada 9; meta anterior de 7/10 ainda nao atingida."
    return resumo


if __name__ == "__main__":
    resumo = comparar(json.loads(OLD.read_text()), json.loads(NEW.read_text()))
    OUT.write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(resumo, indent=2, ensure_ascii=False))
