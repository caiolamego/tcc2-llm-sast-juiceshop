#!/usr/bin/env python3
"""Materializa grupos exploratorios de correcoes a partir da matriz auditada.

Nao escreve no baseline, no catalogo JS001-JS012 ou nos resultados da LLM.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
MATRIX = ROOT / "outputs/auditoria_sast/matriz_desafios.json"
CONFIG = ROOT / "config/candidatos_correcao_exploratorios.yaml"
OUT = ROOT / "outputs/auditoria_sast"
SCANS = {"default", "custom-rules"}


def construir(matriz: dict, config: dict) -> dict:
    alertas = {}
    curtas = {}
    for a in matriz["alertas"]:
        if a["scan"] in SCANS:
            curta = f"{a['scan']}|{a['arquivo']}|{a['inicio']}"
            ref = f"{curta}|{a['regra']}"
            if ref in alertas:
                raise ValueError(f"Referencia ambigua: {ref}")
            alertas[ref] = a
            curtas.setdefault(curta, []).append(a)
    cobertura = set(matriz["desafios_confirmados_por_scan"]["default"])
    cobertura.update(matriz["desafios_confirmados_por_scan"]["custom-rules"])
    usados, desafios_usados, ids = set(), set(), set()
    casos = []
    for caso in config["casos"]:
        ident = caso["id"]
        if ident in ids:
            raise ValueError(f"ID duplicado: {ident}")
        ids.add(ident)
        if caso["prioridade"] not in {"piloto", "posterior"}:
            raise ValueError(f"Prioridade invalida: {ident}")
        chaves = set(caso["desafios"])
        if not chaves or chaves & desafios_usados:
            raise ValueError(f"Desafios vazios ou duplicados: {ident} {chaves & desafios_usados}")
        desafios_usados |= chaves
        evidencias = []
        cobertos = set()
        for ref in caso["alertas"]:
            if ref in usados:
                raise ValueError(f"Alerta reutilizado em casos distintos: {ref}")
            usados.add(ref)
            a = alertas.get(ref)
            if a is None and len(curtas.get(ref, [])) == 1:
                a = curtas[ref][0]
            if a is None or a["triagem"]["status"] != "confirmado":
                raise ValueError(f"Alerta ausente ou nao confirmado: {ident} {ref}")
            vinculos = set(a["triagem"]["desafios_confirmados"])
            if not vinculos <= chaves:
                raise ValueError(f"Alerta cobre desafio fora do grupo: {ident} {ref}")
            cobertos |= vinculos
            evidencias.append({"scan": a["scan"], "regra": a["regra"], "arquivo": a["arquivo"],
                               "inicio": a["inicio"], "fim": a["fim"], "alerta_id": a["id"]})
        if cobertos != chaves:
            raise ValueError(f"Desafio sem alerta confirmado no grupo: {ident} {chaves - cobertos}")
        casos.append({"id": ident, "causa": caso["causa"], "desafios": caso["desafios"],
                      "prioridade": caso["prioridade"], "status": "aguarda_teste_regressao",
                      "evidencias": evidencias})
    if desafios_usados != cobertura:
        raise ValueError(f"Cobertura incompleta: faltam {cobertura - desafios_usados}; extras {desafios_usados - cobertura}")
    # O criterio R legado compara (regra, arquivo). Registra colisao entre
    # causas diferentes sem fingir que um alerta na mesma regra/arquivo e outro.
    assinaturas = {}
    for caso in casos:
        for e in caso["evidencias"]:
            assinaturas.setdefault((e["regra"], e["arquivo"]), set()).add(caso["id"])
    colisoes = [{"regra": regra, "arquivo": arquivo, "casos": sorted(grupos)}
                for (regra, arquivo), grupos in sorted(assinaturas.items()) if len(grupos) > 1]
    return {"commit_alvo": matriz["commit_alvo"], "semgrep_versao": matriz["semgrep_versao"],
            "perfil_candidato": config["perfil_candidato"],
            "aviso": "Perfil remoto p/default ainda nao congelado; nenhum caso pronto para executar LLM.",
            "total_casos": len(casos), "total_desafios": len(desafios_usados),
            "colisoes_assinatura_legada": colisoes, "casos": casos}


def main() -> None:
    matriz = json.loads(MATRIX.read_text(encoding="utf-8"))
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    dados = construir(matriz, config)
    dados["sha256_matriz"] = hashlib.sha256(MATRIX.read_bytes()).hexdigest()
    dados["sha256_config"] = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "candidatos_correcao.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
    with (OUT / "candidatos_correcao.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "causa", "prioridade", "status", "desafios",
                                                 "scan", "regra", "arquivo", "inicio", "fim"])
        writer.writeheader()
        for caso in dados["casos"]:
            for e in caso["evidencias"]:
                writer.writerow({"id": caso["id"], "causa": caso["causa"],
                                 "prioridade": caso["prioridade"], "status": caso["status"],
                                 "desafios": ";".join(caso["desafios"]), **{k: e[k] for k in
                                 ("scan", "regra", "arquivo", "inicio", "fim")}})
    print(f"{dados['total_casos']} causas candidatas; {dados['total_desafios']} desafios; "
          f"{len(dados['colisoes_assinatura_legada'])} colisao(oes) na assinatura antiga")


if __name__ == "__main__":
    main()
