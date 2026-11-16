"""Expansao adicional explicitamente solicitada apos rodada 10."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402

import json
from scripts.relatorios.relatorio_rodada2 import ROOT, resumir
from scripts.relatorios.relatorio_rodada10 import PRIORITARIOS

OLD = ROOT / "outputs/auditoria_sast/rodada10/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada11/matriz_desafios.json"
ALVOS = {"timingAttackChallenge", "emailLeakChallenge"}
PERFIS = {"default", "custom-rules", *(f"rodada{i}" for i in range(2, 12))}


def comparar(antes, depois):
    for campo in ("revisoes_associacoes", "revisoes_sha256"):
        if antes.get(campo) != depois.get(campo):
            raise ValueError("Historico SSTI alterado")
    result = resumir(antes, depois, novo_scan="rodada11", perfis=PERFIS)
    result["candidatos_incluidos"] = sorted(ALVOS & set(result["novos_desafios_confirmados"]))
    confirmed = {d["key"] for d in depois["desafios"] if d["confirmacao"] == "confirmado"}
    result["prioritarios_fixos"] = sorted(PRIORITARIOS)
    result["prioritarios_confirmados"] = sorted(PRIORITARIOS & confirmed)
    result["condicao_emailLeakChallenge"] = "Somente origem distinta same-site com sessao valida e controle de subdominio irmao; cross-site Lax nao reproduziu vazamento; Chromium 121 testado."
    result["nota_escopo"] = "Rodada adicional autorizada apos meta anterior. Nao altera encerramento historico da rodada 10 nem inicia outras rodadas. Consolidacao de causas continua pendente."
    return result


if __name__ == "__main__":
    result = comparar(json.loads(OLD.read_text()), json.loads(NEW.read_text()))
    (NEW.parent / "resumo.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
