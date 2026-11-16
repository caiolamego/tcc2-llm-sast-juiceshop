"""Rodada 10: cupons; compara sem modificar alertas historicos."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402

import json
from scripts.relatorios.relatorio_rodada2 import ROOT, resumir

OLD = ROOT / "outputs/auditoria_sast/rodada9/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada10/matriz_desafios.json"
OUT = NEW.parent / "resumo.json"
PERFIS = {"default", "custom-rules", *(f"rodada{i}" for i in range(2, 11))}
ALVOS = {"forgedCouponChallenge", "manipulateClockChallenge"}
PRIORITARIOS = {
    "dataExportChallenge", "negativeOrderChallenge", "registerAdminChallenge",
    "forgedFeedbackChallenge", "lfrChallenge", "changeProductChallenge",
    "forgedCouponChallenge", "manipulateClockChallenge", "timingAttackChallenge", "emailLeakChallenge"
}


def comparar(antes, depois):
    for campo in ("revisoes_associacoes", "revisoes_sha256"):
        if antes.get(campo) != depois.get(campo):
            raise ValueError("Historico SSTI alterado")
    resumo = resumir(antes, depois, novo_scan="rodada10", perfis=PERFIS)
    resumo["candidatos_rodada"] = sorted(ALVOS)
    resumo["candidatos_incluidos"] = sorted(ALVOS & set(resumo["novos_desafios_confirmados"]))
    confirmados = {d["key"] for d in depois["desafios"] if d["confirmacao"] == "confirmado"}
    resumo["prioritarios_fixos"] = sorted(PRIORITARIOS)
    resumo["prioritarios_confirmados"] = sorted(PRIORITARIOS & confirmados)
    resumo["meta_7_de_10_atingida"] = len(PRIORITARIOS & confirmados) >= 7
    resumo["prioritarios_restantes"] = sorted(PRIORITARIOS - confirmados)
    resumo["nota_escopo"] = "Encerrar expansao ao concluir rodada 10; nao iniciar concorrencia/JSONP. Selecao versionada de causas para correcao ainda requer consolidacao separada."
    return resumo


if __name__ == "__main__":
    resumo = comparar(json.loads(OLD.read_text()), json.loads(NEW.read_text()))
    OUT.write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(resumo, indent=2, ensure_ascii=False))
