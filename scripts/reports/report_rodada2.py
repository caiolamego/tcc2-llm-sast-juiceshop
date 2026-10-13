#!/usr/bin/env python3
"""Compara a matriz historica e a rodada 2 sem modificar o baseline."""
from __future__ import annotations

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402


import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

from scripts.audit.review_associations import aplicar_revisoes


ROOT = RAIZ_REPO
OLD = ROOT / "outputs/auditoria_sast/matriz_desafios.json"
NEW = ROOT / "outputs/auditoria_sast/rodada2/matriz_desafios.json"
OUT = ROOT / "outputs/auditoria_sast/rodada2/resumo.json"
FOCUS = {"default", "custom-rules", "rodada2"}


def resumir(antes: dict, depois: dict, novo_scan: str = "rodada2",
            perfis: set[str] | None = None, revisoes: list[dict] | None = None) -> dict:
    if perfis is None:
        perfis = FOCUS
    if antes["commit_alvo"] != depois["commit_alvo"] or antes["semgrep_versao"] != depois["semgrep_versao"]:
        raise ValueError("Alvo ou versao do Semgrep mudou")
    if (len(depois["desafios"]) != 113 or len({d["key"] for d in depois["desafios"]}) != 113
            or depois["total_desafios"] != 113):
        raise ValueError("A nova matriz nao contem 113 desafios unicos")
    for nome, scan in antes["resumo_scans"].items():
        if depois["resumo_scans"].get(nome) != scan:
            raise ValueError(f"Scan historico alterado: {nome}")
    esperados = deepcopy(antes["alertas"])
    if revisoes is not None:
        historico = aplicar_revisoes(esperados, revisoes, {d["key"] for d in depois["desafios"]})
        if depois.get("revisoes_associacoes") != historico:
            raise ValueError("Historico de revisoes diverge da configuracao revisada")
        por_id = {a["id"]: a for a in esperados}
        for revisao in historico:
            alerta = por_id[revisao["alerta_id"]]
            for key in revisao["desafios_adicionais"]:
                if any(v["desafio"] == key for v in alerta["associacoes"]):
                    raise ValueError("Revisao de associacao preexistente exige analise especifica")
                alerta["associacoes"].append({"desafio": key, "relacao": "confirmacao_manual_sem_marcador"})
    antigo = {a["id"]: a for a in esperados}
    atual = {a["id"]: deepcopy(a) for a in depois["alertas"]}
    if revisoes is not None:
        for a in list(antigo.values()) + list(atual.values()):
            a["associacoes"].sort(key=lambda v: (v["desafio"], v["relacao"]))
    if not all(atual.get(k) == v for k, v in antigo.items()):
        raise ValueError("Alerta ou triagem historica mudou")
    novos = [a for a in depois["alertas"] if a["scan"] == novo_scan]
    if len(novos) != depois["resumo_scans"][novo_scan]["ocorrencias"]:
        raise ValueError("Contagem de novos alertas inconsistente")
    antes_desafios = {d["key"] for d in antes["desafios"] if d["confirmacao"] == "confirmado"}
    depois_desafios = {d["key"] for d in depois["desafios"] if d["confirmacao"] == "confirmado"}
    if antes_desafios - depois_desafios:
        raise ValueError("Desafio antes confirmado perdeu confirmacao")
    foco = [a for a in depois["alertas"] if a["scan"] in perfis]
    return {
        "commit_alvo": depois["commit_alvo"], "semgrep_versao": depois["semgrep_versao"],
        "alertas_novos": len(novos),
        "triagem_novos": dict(Counter(a["triagem"]["status"] for a in novos)),
        "alertas_perfil_ampliado": len(foco),
        "triagem_perfil_ampliado": dict(Counter(a["triagem"]["status"] for a in foco)),
        "desafios_confirmados_antes": len(antes_desafios),
        "desafios_confirmados_depois": len(depois_desafios),
        "novos_desafios_confirmados": sorted(depois_desafios - antes_desafios),
        "avisos_parsing_novos": depois["resumo_scans"][novo_scan]["avisos_parsing"],
        "nota": "Contagens de desafios nao equivalem a recall sobre os 113 nem a numero de correcoes independentes."
    }


def main() -> None:
    antes = json.loads(OLD.read_text(encoding="utf-8"))
    depois = json.loads(NEW.read_text(encoding="utf-8"))
    resumo = resumir(antes, depois)
    OUT.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
