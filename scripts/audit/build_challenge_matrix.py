#!/usr/bin/env python3
"""Matriz exploratoria desafio -> codigo -> regra -> alerta -> triagem.

Nunca altera outputs/sast_antes ou o catalogo principal. Exemplo:
  python3 scripts/audit/build_challenge_matrix.py --worktree /tmp/tcc-juiceshop-audit
"""
from __future__ import annotations

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402


import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import yaml

from scripts.audit.review_associations import aplicar_revisoes


RAIZ = RAIZ_REPO
SAIDA = RAIZ / "outputs/auditoria_sast"
SCANS = {
    "baseline": RAIZ / "outputs/sast_antes/baseline_raw.json",
    "default": SAIDA / "default.json",
    "security-audit": SAIDA / "security-audit.json",
    "angular-sanitizer-bypass": SAIDA / "angular-sanitizer-bypass.json",
    "custom-rules": SAIDA / "custom-rules.json",
}
MARCADOR = re.compile(r"(?:\/\/|<!--)\s*vuln-code-snippet\s+(start|end|vuln-line)\s+(.+?)\s*(?:-->|\*\/)?\s*$")
EXTENSOES = {".ts", ".js", ".html", ".sol"}


def nomes_marcador(texto: str) -> list[str]:
    return [n for n in re.split(r"[\s,]+", texto) if n]


def extrair_evidencias(worktree: Path, chaves: set[str]) -> dict[str, list[dict]]:
    arquivos = subprocess.run(["git", "ls-files", "-z"], cwd=worktree, check=True,
                             capture_output=True).stdout.decode("utf-8").split("\0")
    evidencias: dict[str, list[dict]] = {key: [] for key in chaves}
    for rel in arquivos:
        if not rel or Path(rel).suffix not in EXTENSOES or "codefixes" in Path(rel).parts:
            continue
        caminho = worktree / rel
        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
        abertos: dict[str, int] = {}
        vulneraveis: dict[str, list[int]] = {}
        for numero, linha in enumerate(linhas, 1):
            m = MARCADOR.search(linha)
            if not m:
                continue
            for key in nomes_marcador(m.group(2)):
                if key not in chaves:
                    raise ValueError(f"Marcador desconhecido: {rel}:{numero} {key}")
                if m.group(1) == "start":
                    if key in abertos:
                        raise ValueError(f"Bloco duplicado: {rel}:{numero} {key}")
                    abertos[key] = numero
                    vulneraveis[key] = []
                elif m.group(1) == "vuln-line":
                    if key not in abertos:
                        raise ValueError(f"Linha vulneravel fora do bloco: {rel}:{numero} {key}")
                    vulneraveis[key].append(numero)
                else:
                    if key not in abertos:
                        raise ValueError(f"Fim de bloco sem inicio: {rel}:{numero} {key}")
                    evidencias[key].append({"arquivo": rel, "inicio": abertos.pop(key),
                                            "fim": numero, "linhas_vulneraveis": vulneraveis.pop(key)})
        if abertos:
            raise ValueError(f"Blocos sem fim em {rel}: {sorted(abertos)}")
    return evidencias


def relacao(achado: dict, blocos: list[dict]) -> str | None:
    mesmo_arquivo = False
    a, b = achado["inicio"], achado["fim"]
    for bloco in blocos:
        if bloco["arquivo"] != achado["arquivo"]:
            continue
        mesmo_arquivo = True
        if any(a <= linha <= b for linha in bloco["linhas_vulneraveis"]):
            return "linha_vulneravel"
    for bloco in blocos:
        if bloco["arquivo"] == achado["arquivo"] and a <= bloco["fim"] and bloco["inicio"] <= b:
            return "bloco_marcado"
    return "mesmo_arquivo_suspeita" if mesmo_arquivo else None


def carregar_alertas(worktree: Path, scans: dict[str, Path], versao: str) -> tuple[list[dict], dict]:
    alertas: list[dict] = []
    resumo: dict = {}
    for nome, caminho in scans.items():
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(dados.get("results"), list):
            raise ValueError(f"Scan sem results: {caminho}")
        if dados.get("version") != versao:
            raise ValueError(f"Versao do scan {nome} difere do baseline: {dados.get('version')} != {versao}")
        resumo[nome] = {"ocorrencias": len(dados["results"]), "avisos_parsing": len(dados.get("errors", [])),
                        "sha256_json": hashlib.sha256(caminho.read_bytes()).hexdigest()}
        for item in dados["results"]:
            rel = item["path"].removeprefix("./")
            if not (worktree / rel).is_file():
                raise ValueError(f"Alerta aponta arquivo ausente: {nome} {rel}")
            inicio, fim = item["start"]["line"], item["end"]["line"]
            tamanho = len((worktree / rel).read_text(encoding="utf-8", errors="replace").splitlines())
            if not 1 <= inicio <= fim <= tamanho:
                raise ValueError(f"Linha invalida: {nome} {rel}:{inicio}-{fim}")
            regra = item["check_id"]
            identidade = "|".join([nome, regra, rel, str(inicio), str(fim)])
            alertas.append({"id": hashlib.sha256(identidade.encode()).hexdigest()[:16],
                            "scan": nome, "regra": regra, "arquivo": rel, "inicio": inicio,
                            "fim": fim, "severidade": item.get("extra", {}).get("severity")})
    alertas.sort(key=lambda a: (a["scan"], a["arquivo"], a["inicio"], a["regra"]))
    return alertas, resumo


def aplicar_triagem(alertas: list[dict], regras: list[dict], chaves: set[str]) -> None:
    usados = set()
    for alerta in alertas:
        alerta["triagem"] = {"status": "pendente", "motivo": None, "desafios_confirmados": []}
        for i, regra in enumerate(regras):
            if (alerta["regra"] == regra["regra"] and alerta["arquivo"] == regra["arquivo"]
                    and alerta["inicio"] == regra["linha"]
                    and ("scan" not in regra or alerta["scan"] == regra["scan"])):
                if not set(regra.get("desafios", [])) <= chaves:
                    raise ValueError(f"Triagem referencia desafio inexistente: {regra}")
                if regra["status"] not in {"confirmado", "falso_positivo", "inconclusivo"}:
                    raise ValueError(f"Status de triagem invalido: {regra}")
                alerta["triagem"] = {"status": regra["status"], "motivo": regra["motivo"],
                                     "desafios_confirmados": regra.get("desafios", []),
                                     "sem_marcador": regra.get("sem_marcador", False)}
                usados.add(i)
                break
    nao_encontrados = set(range(len(regras))) - usados
    if nao_encontrados:
        raise ValueError(f"Triagens sem alerta correspondente: {[regras[i] for i in sorted(nao_encontrados)]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--triagem", type=Path, default=RAIZ / "config/auditoria_desafios.yaml")
    parser.add_argument("--triagem-extra", type=Path, action="append", default=[],
                        help="Triagem adicional para scans novos, sem editar a triagem historica")
    parser.add_argument("--scan-extra", action="append", default=[], metavar="NOME=JSON",
                        help="Inclui um scan arquivado adicional na nova matriz")
    parser.add_argument("--revisoes", type=Path,
                        help="Associacoes adicionais versionadas para alertas ja confirmados")
    parser.add_argument("--saida", type=Path, default=SAIDA)
    args = parser.parse_args()
    if (args.scan_extra or args.revisoes) and args.saida.resolve() == SAIDA.resolve():
        parser.error("use --saida com um diretorio novo para preservar a matriz historica")
    worktree = args.worktree.resolve()
    meta = json.loads((RAIZ / "outputs/sast_antes/catalogo_meta.json").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=worktree, check=True,
                            capture_output=True, text=True).stdout.strip()
    if commit != meta["commit_alvo"]:
        parser.error(f"Commit alvo incorreto: {commit} != {meta['commit_alvo']}")
    desafios = yaml.safe_load((worktree / "data/static/challenges.yml").read_text(encoding="utf-8"))
    chaves = [item["key"] for item in desafios]
    if len(chaves) != len(set(chaves)):
        raise ValueError("Chaves de desafio duplicadas")
    conjunto = set(chaves)
    config = yaml.safe_load(args.triagem.read_text(encoding="utf-8"))
    extras = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in args.triagem_extra]
    candidatos = dict(config.get("regras_candidatas", {}))
    for extra in extras:
        for chave, regras in extra.get("regras_candidatas", {}).items():
            candidatos[chave] = sorted(set(candidatos.get(chave, []) + regras))
    if not set(candidatos) <= conjunto:
        raise ValueError(f"Regras candidatas para chaves desconhecidas: {set(candidatos) - conjunto}")
    evidencias = extrair_evidencias(worktree, conjunto)
    codefixes = {p.name.removesuffix(".info.yml") for p in (worktree / "data/static/codefixes").glob("*.info.yml")}
    if not codefixes <= conjunto:
        raise ValueError("Codefix referencia desafio desconhecido")
    scans = dict(SCANS)
    for spec in args.scan_extra:
        nome, separador, caminho = spec.partition("=")
        if not separador or not nome or not caminho or nome in scans:
            parser.error(f"--scan-extra invalido ou duplicado: {spec}")
        scans[nome] = Path(caminho).resolve()
    alertas, resumos = carregar_alertas(worktree, scans, meta["semgrep_versao"])
    aplicar_triagem(alertas, config.get("triagem", []) +
                   [regra for extra in extras for regra in extra.get("triagem", [])], conjunto)
    revisoes = yaml.safe_load(args.revisoes.read_text(encoding="utf-8")) if args.revisoes else []
    historico_revisoes = aplicar_revisoes(alertas, revisoes, conjunto)
    matriz = []
    for item in desafios:
        key = item["key"]
        blocos = evidencias[key]
        ext = {Path(b["arquivo"]).suffix for b in blocos}
        associados = []
        for alerta in alertas:
            tipo = relacao(alerta, blocos)
            if tipo:
                associados.append({"alerta_id": alerta["id"], "relacao": tipo})
                alerta.setdefault("associacoes", []).append({"desafio": key, "relacao": tipo})
        confirmados = [a for a in alertas if key in a["triagem"]["desafios_confirmados"]]
        evidencias_manuais = []
        for alerta in confirmados:
            vinculos = [v for v in associados if v["alerta_id"] == alerta["id"]]
            if any(v["relacao"] in {"linha_vulneravel", "bloco_marcado"} for v in vinculos):
                continue
            if not alerta["triagem"].get("sem_marcador"):
                raise ValueError(f"Confirmacao sem marcador exige sem_marcador: {alerta['id']} {key}")
            for v in vinculos:
                v["relacao"] = "confirmacao_manual_sem_marcador"
            for v in alerta.get("associacoes", []):
                if v["desafio"] == key:
                    v["relacao"] = "confirmacao_manual_sem_marcador"
            if not vinculos:
                associados.append({"alerta_id": alerta["id"], "relacao": "confirmacao_manual_sem_marcador"})
                alerta.setdefault("associacoes", []).append(
                    {"desafio": key, "relacao": "confirmacao_manual_sem_marcador"})
            evidencias_manuais.append({"arquivo": alerta["arquivo"], "inicio": alerta["inicio"],
                                       "fim": alerta["fim"], "alerta_id": alerta["id"],
                                       "motivo": alerta["triagem"]["motivo"]})
        detectabilidade = ("candidato_sast" if ext & {".ts", ".js", ".html"} else
                           "fora_escopo_sast_js_ts" if ext == {".sol"} else
                           "candidato_sast_revisado" if evidencias_manuais else "indeterminado")
        matriz.append({"key": key, "nome": item["name"], "categoria": item["category"],
                       "coding_challenge": key in codefixes, "detectabilidade": detectabilidade,
                       "evidencias": blocos, "evidencias_manuais": evidencias_manuais,
                       "regras_candidatas": candidatos.get(key, []),
                       "alertas_associados": associados,
                       "confirmacao": "confirmado" if confirmados else "pendente",
                       "alertas_confirmados": [a["id"] for a in confirmados]})
    for alerta in alertas:
        alerta.setdefault("associacoes", [])
        for key in alerta["triagem"]["desafios_confirmados"]:
            if not any(a["desafio"] == key and a["relacao"] in {"linha_vulneravel", "bloco_marcado",
                                                          "confirmacao_manual_sem_marcador"}
                       for a in alerta["associacoes"]):
                raise ValueError(f"Confirmacao sem sobreposicao com marcador: {alerta['id']} {key}")
    cobertura = {nome: sorted({key for a in alertas if a["scan"] == nome for key in
                             a["triagem"]["desafios_confirmados"]}) for nome in scans}
    novos_custom = sorted(set(cobertura["custom-rules"]) - set(cobertura["baseline"]))
    uniao_confirmada = sorted(set().union(*(set(itens) for itens in cobertura.values())))
    regras_locais = {str(p.relative_to(RAIZ)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((RAIZ / "rules").rglob("*.yaml"))}
    dados = {"commit_alvo": commit, "semgrep_versao": meta["semgrep_versao"],
             "fonte_desafios": "data/static/challenges.yml", "total_desafios": len(matriz),
             "total_coding_challenges": len(codefixes), "resumo_scans": resumos,
             "regras_locais_sha256": regras_locais,
             "triagem": dict(Counter(a["triagem"]["status"] for a in alertas)),
             "desafios_confirmados_por_scan": cobertura,
             "novos_desafios_confirmados_custom_vs_baseline": novos_custom,
             "total_desafios_confirmados_uniao": len(uniao_confirmada),
             "desafios": matriz, "alertas": alertas}
    if args.revisoes:
        dados["revisoes_associacoes"] = historico_revisoes
        dados["revisoes_sha256"] = hashlib.sha256(args.revisoes.read_bytes()).hexdigest()
    args.saida.mkdir(parents=True, exist_ok=True)
    json_path = args.saida / "matriz_desafios.json"
    json_path.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_path = args.saida / "matriz_desafios.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        campos = ["key", "nome", "categoria", "coding_challenge", "detectabilidade", "evidencias",
                  "regras_candidatas", "confirmacao", "alerta_id", "scan", "regra", "arquivo",
                  "linhas", "relacao", "triagem", "motivo"]
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        por_id = {a["id"]: a for a in alertas}
        for desafio in matriz:
            base = {k: desafio[k] for k in ["key", "nome", "categoria", "coding_challenge",
                                             "detectabilidade", "confirmacao"]}
            base["evidencias"] = "; ".join(f"{b['arquivo']}:{b['inicio']}-{b['fim']}"
                                                  for b in desafio["evidencias"] + desafio["evidencias_manuais"])
            base["regras_candidatas"] = "; ".join(desafio["regras_candidatas"])
            for vinculo in desafio["alertas_associados"] or [None]:
                linha = dict(base)
                if vinculo:
                    a = por_id[vinculo["alerta_id"]]
                    linha.update({"alerta_id": a["id"], "scan": a["scan"], "regra": a["regra"],
                                  "arquivo": a["arquivo"], "linhas": f"{a['inicio']}-{a['fim']}",
                                  "relacao": vinculo["relacao"], "triagem": a["triagem"]["status"],
                                  "motivo": a["triagem"]["motivo"]})
                writer.writerow(linha)
    print(f"{len(matriz)} desafios; {len(codefixes)} Coding Challenges; "
          f"{len(alertas)} alertas; triagem {dados['triagem']}")
    print(f"Matriz: {json_path} e {csv_path}")


if __name__ == "__main__":
    main()
