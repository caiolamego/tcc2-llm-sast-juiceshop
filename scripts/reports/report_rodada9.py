"""Compara rodada 9 completa com rodada 8 sem modificar historia."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import json
from scripts.reports.report_rodada2 import ROOT, resumir

OLD = ROOT / "outputs/auditoria_sast/rodada8/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada9/matriz_desafios.json"
OUT = NEW.parent / "resumo.json"
PERFIS = {"default", "custom-rules", *(f"rodada{i}" for i in range(2, 10))}
ALVOS = {"lfrChallenge", "changeProductChallenge"}


def comparar(antes, depois):
    for campo in ("revisoes_associacoes", "revisoes_sha256"):
        if antes.get(campo) != depois.get(campo):
            raise ValueError("Historico SSTI alterado")
    resumo = resumir(antes, depois, novo_scan="rodada9", perfis=PERFIS)
    resumo["candidatos_rodada"] = sorted(ALVOS)
    resumo["candidatos_incluidos"] = sorted(ALVOS & set(resumo["novos_desafios_confirmados"]))
    resumo["scan_utilizado"] = "rodada9/scan_completo/rodada9.json"
    resumo["tentativa_inicial"] = "rodada9.json: timeout de autorizacao em server.ts; preservado, fora da matriz consolidada"
    resumo["nota_escopo"] = "Encerrar rodada 9. Seis dos dez prioritarios incluidos; nao iniciar rodada 10 automaticamente."
    return resumo


if __name__ == "__main__":
    resumo = comparar(json.loads(OLD.read_text()), json.loads(NEW.read_text()))
    OUT.write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(resumo, indent=2, ensure_ascii=False))
