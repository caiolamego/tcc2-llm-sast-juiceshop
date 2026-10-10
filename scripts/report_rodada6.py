#!/usr/bin/env python3
"""Distingue novos alertas de revisoes de associacoes de alertas antigos."""
import hashlib
import json

import yaml

from report_rodada2 import ROOT, resumir

OLD = ROOT / "outputs/auditoria_sast/rodada5/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada6/matriz_desafios.json"
OUT = ROOT / "outputs/auditoria_sast/rodada6/resumo.json"
REVISOES = ROOT / "config/revisoes_associacoes_rodada6.yaml"
PERFIS = {"default", "custom-rules", "rodada2", "rodada3", "rodada4", "rodada5", "rodada6"}


def comparar(antes: dict, depois: dict) -> dict:
    revisoes = yaml.safe_load(REVISOES.read_text(encoding="utf-8"))
    if depois.get("revisoes_sha256") != hashlib.sha256(REVISOES.read_bytes()).hexdigest():
        raise ValueError("Hash das revisoes diverge da configuracao")
    resumo = resumir(antes, depois, novo_scan="rodada6", perfis=PERFIS, revisoes=revisoes)
    anteriores = {d["key"] for d in antes["desafios"] if d["confirmacao"] == "confirmado"}
    novos = {k for a in depois["alertas"] if a["scan"] == "rodada6"
             for k in a["triagem"]["desafios_confirmados"]} - anteriores
    revisados = {k for r in revisoes for k in r["desafios_adicionais"]} - anteriores - novos
    if novos | revisados != set(resumo["novos_desafios_confirmados"]):
        raise ValueError("Nova cobertura sem origem rastreada")
    resumo["novos_desafios_por_alertas_novos"] = sorted(novos)
    resumo["novos_desafios_apenas_por_revisao"] = sorted(revisados)
    resumo["alertas_antigos_com_associacao_ampliada"] = len(revisoes)
    return resumo


def main() -> None:
    resumo = comparar(json.loads(OLD.read_text(encoding="utf-8")),
                      json.loads(NEW.read_text(encoding="utf-8")))
    OUT.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
