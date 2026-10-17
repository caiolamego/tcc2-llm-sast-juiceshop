#!/usr/bin/env python3
"""Constroi o catalogo de issues elegiveis a partir do baseline SAST (F3.2),
aplicando o protocolo de filtragem deterministico da Decisao D1. Roda uma
unica vez por execucao do baseline -- NAO chama o semgrep de novo, so le o
JSON ja gerado. Grava outputs/sast_antes/catalogo_issues.json com TODOS os
findings (elegiveis e excluidos, cada um com o motivo), para auditoria, e
outputs/sast_antes/catalogo_meta.json com os totais de cada etapa (brutos,
duplicatas removidas, total apos dedupe) -- sem isso esses numeros so
existiam no print do terminal e se perdiam (ver caderno, F3.6).

IDs estaveis: com --catalogo-anterior, um achado com a mesma assinatura
mantem o caso_id antigo e os novos continuam a numeracao (catalogo v2 sobre
o v1, 2026-10-13). triagem_manual vem de config/triagem_manual.yaml e nao
exclui nada (protocolo, Secao 3, passo 7).

Uso:
    python scripts/build_issue_catalog.py [--worktree workspace/wt-1] [--catalogo-anterior outputs/sast_antes/catalogo_issues_v1.json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml
from dotenv import dotenv_values

RAIZ_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_REPO / "src"))
from pipeline.sast.semgrep_client import RULESETS, carregar_resultados, assinatura, ler_exclusoes  # noqa: E402
from pipeline.sast.filtro import SEVERIDADES_ACEITAS, filtrar  # noqa: E402

BASELINE_JSON = RAIZ_REPO / "outputs" / "sast_antes" / "baseline_raw.json"
SAIDA = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_issues.json"
SAIDA_META = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_meta.json"

MAPA_CWE = RAIZ_REPO / "config" / "mapa_cwe_vuln.yaml"
MAPA_OWASP = RAIZ_REPO / "config" / "mapa_owasp.yaml"
MAPA_RAG = RAIZ_REPO / "config" / "mapa_categoria_rag.yaml"
TRIAGEM = RAIZ_REPO / "config" / "triagem_manual.yaml"
EXCLUSOES = RAIZ_REPO / "config" / "semgrepignore"
# Copia de referencia das regras (ver o README da pasta): pode divergir do
# que o registro executou na varredura.
DIR_REGRAS = RAIZ_REPO / "config" / "semgrep-rules-referencia"

# Normaliza os dois esquemas em 2 buckets, para relatorios nao mostrarem
# "WARNING" e "MEDIUM" como se fossem niveis diferentes (sao o mesmo).
NORMALIZACAO_SEVERIDADE = {
    "ERROR": "ALTA", "HIGH": "ALTA", "CRITICAL": "ALTA",
    "WARNING": "MEDIA", "MEDIUM": "MEDIA",
}
LIMITE_ARQUIVO_COMPLETO = 250  # linhas -- ver Decisao D3
# Folga do trecho gravado no catalogo (Secao 3.5 do TCC 1). O Semgrep sem
# login devolve 'requires login' em extra.lines, entao o trecho e lido do
# arquivo no worktree (caderno, 2026-10-07).
FOLGA_TRECHO = 3


def carregar_yaml(caminho: Path) -> dict:
    if not caminho.exists():
        raise FileNotFoundError(f"Config nao encontrado: {caminho}")
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def extrair_cwe_numero(cwe_strs: tuple[str, ...]) -> str | None:
    """De 'CWE-89: Improper Neutralization...' extrai 'CWE-89'."""
    for c in cwe_strs:
        m = re.match(r"(CWE-\d+)", c)
        if m:
            return m.group(1)
    return None


def extrair_owasp_2021(owasp_strs: tuple[str, ...]) -> str | None:
    """De 'A03:2021 - Injection' extrai 'A03:2021'."""
    for o in owasp_strs:
        m = re.match(r"(A\d+:2021)", o)
        if m:
            return m.group(1)
    return None


def contexto_do_arquivo(worktree: Path, caminho_relativo: str) -> tuple[int, str]:
    """Le o arquivo no worktree para saber o total de linhas e decidir o
    modo_contexto (Decisao D3). Se o arquivo nao existir mais (raro), assume
    janela por seguranca."""
    alvo = worktree / caminho_relativo
    try:
        total = len(alvo.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0, "janela_contexto"
    modo = "arquivo_completo" if total <= LIMITE_ARQUIVO_COMPLETO else "janela_contexto"
    return total, modo


def extrair_trecho(worktree: Path, caminho_relativo: str, inicio: int, fim: int) -> tuple[str, int, int]:
    """Linhas inicio-FOLGA .. fim+FOLGA do arquivo (1-indexado, inclusivo)."""
    linhas = (worktree / caminho_relativo).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    a = max(1, inicio - FOLGA_TRECHO)
    b = min(len(linhas), fim + FOLGA_TRECHO)
    return "".join(linhas[a - 1:b]), a, b


def _padroes(no) -> list[str]:
    """Achata os valores de 'pattern' de um bloco de pattern-sanitizers."""
    if isinstance(no, dict):
        achados = [no["pattern"]] if isinstance(no.get("pattern"), str) else []
        for v in no.values():
            if isinstance(v, (dict, list)):
                achados += _padroes(v)
        return achados
    if isinstance(no, list):
        return [p for item in no for p in _padroes(item)]
    return []


def info_regra(check_id: str) -> tuple[str | None, list[str] | None]:
    """(modo_regra, saneadores_regra) pela copia de referencia.
    check_id a.b.c.arquivo.id -> a/b/c/arquivo.yaml, regra 'id'.
    (None, None) se a regra nao estiver na copia."""
    *partes, id_regra = check_id.split(".")
    arq = DIR_REGRAS.joinpath(*partes[:-1], partes[-1] + ".yaml") if partes else None
    if not arq or not arq.exists():
        return None, None
    for regra in (yaml.safe_load(arq.read_text(encoding="utf-8")) or {}).get("rules", []):
        if regra.get("id") == id_regra:
            return regra.get("mode", "search"), _padroes(regra.get("pattern-sanitizers", []))
    return None, None


def commit_do_worktree(worktree: Path) -> str:
    """Commit em que o worktree esta, conferido contra JUICESHOP_COMMIT do .env."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=worktree, capture_output=True,
                          text=True, check=True, timeout=30).stdout.strip()
    esperado = dotenv_values(RAIZ_REPO / ".env").get("JUICESHOP_COMMIT")
    if esperado and head != esperado:
        raise SystemExit(f"{worktree.name} esta em {head}, mas o .env fixa {esperado}")
    return head


def funil(findings) -> dict:
    """Contagem depois de cada passo da Secao 3 (2 a 5), na ordem do protocolo.
    O catalogo deduplica antes de filtrar; o resultado final e o mesmo, porque
    categoria, severidade e CWE sao da regra, iguais em todo o (check_id, path)."""
    f2 = [f for f in findings if f.category == "security"]
    f3 = [f for f in f2 if f.severity in SEVERIDADES_ACEITAS]
    f4 = [f for f in f3 if f.cwe]
    return {"1_brutos_apos_exclusao_de_caminhos": len(findings), "2_categoria_security": len(f2),
            "3_severidade": len(f3), "4_com_cwe": len(f4),
            "5_dedup_check_id_path": len({(f.check_id, f.path) for f in f4})}


def carregar_triagem() -> dict[tuple[str, str, int], str]:
    dados = carregar_yaml(TRIAGEM).get("triagem", [])
    return {(t["check_id"], t["arquivo"], int(t["linha"])): t["status"] for t in dados}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", default="workspace/wt-1")
    ap.add_argument("--catalogo-anterior", default=None,
                    help="mantem o caso_id de achados com a mesma assinatura")
    args = ap.parse_args()
    worktree = (RAIZ_REPO / args.worktree).resolve()

    mapa_cwe = carregar_yaml(MAPA_CWE)
    mapa_owasp = carregar_yaml(MAPA_OWASP)
    mapa_rag = carregar_yaml(MAPA_RAG)
    triagem = carregar_triagem()
    ids_anteriores: dict[str, str] = {}
    if args.catalogo_anterior:
        anterior = json.loads((RAIZ_REPO / args.catalogo_anterior).read_text(encoding="utf-8"))
        ids_anteriores = {c["assinatura"]: c["caso_id"] for c in anterior if c.get("caso_id")}
    proximo_id = max((int(i[2:]) for i in ids_anteriores.values()), default=0)

    if not BASELINE_JSON.exists():
        raise SystemExit(f"Baseline nao encontrado: {BASELINE_JSON}. Rode F3.2 primeiro.")

    commit_alvo = commit_do_worktree(worktree)
    versao_semgrep = json.loads(BASELINE_JSON.read_text(encoding="utf-8")).get("version")
    findings = carregar_resultados(BASELINE_JSON, worktree)
    findings_brutos = len(findings)
    print(f"Findings brutos carregados: {findings_brutos}")

    vistos: set[tuple[str, str]] = set()  # dedupe por (check_id, path) -- passo 5 do D1
    catalogo: list[dict] = []
    contador = 0
    duplicatas = 0

    for f in findings:
        chave_dedupe = (f.check_id, f.path)
        if chave_dedupe in vistos:
            duplicatas += 1
            continue
        vistos.add(chave_dedupe)

        elegivel, motivo = filtrar(f)
        cwe_num = extrair_cwe_numero(f.cwe)
        owasp_2021 = extrair_owasp_2021(f.owasp)

        sigla_vuln = mapa_cwe.get(cwe_num, "OUTRO") if elegivel and cwe_num else None
        owasp_2025 = mapa_owasp.get(owasp_2021) if elegivel and owasp_2021 else None
        categoria_rag = mapa_rag.get(sigla_vuln) if elegivel and sigla_vuln else None

        modo_regra, saneadores_regra = info_regra(f.check_id)
        trecho, trecho_ini, trecho_fim = extrair_trecho(worktree, f.path, f.start_line, f.end_line)

        if elegivel:
            total_linhas, modo_contexto = contexto_do_arquivo(worktree, f.path)
        else:
            total_linhas, modo_contexto = None, None

        entrada = {
            "caso_id": None,
            "assinatura": assinatura(f),
            "check_id": f.check_id,
            # metadata.subcategory (vuln/audit/guardrail) e, como conferencia,
            # '.audit.' no check_id. Nao coincidem neste baseline (caderno).
            "subcategoria_regra": ",".join(f.subcategory) or None,
            "audit_no_check_id": ".audit." in f.check_id,
            "modo_regra": modo_regra,
            "saneadores_regra": saneadores_regra,
            "arquivo": f.path,
            "linha_inicio": f.start_line,
            "linha_fim": f.end_line,
            "severidade": f.severity,
            "severidade_normalizada": NORMALIZACAO_SEVERIDADE.get(f.severity),
            "mensagem": f.message,
            "cwe": list(f.cwe),
            "owasp_2021": list(f.owasp),
            "owasp_2025": owasp_2025,
            "sigla_vuln": sigla_vuln,
            "categoria_rag": categoria_rag,
            "trecho": trecho,
            "trecho_linha_inicio": trecho_ini,
            "trecho_linha_fim": trecho_fim,
            "linhas_arquivo": total_linhas,
            "modo_contexto": modo_contexto,
            "marcador_juiceshop": None,   # preenchido em F3.5
            "triagem_manual": triagem.get((f.check_id, f.path, f.start_line), "nao_triado"),
            "elegivel": elegivel,
            "motivo_exclusao": motivo,
        }

        if elegivel:
            contador += 1
            if entrada["assinatura"] in ids_anteriores:
                entrada["caso_id"] = ids_anteriores[entrada["assinatura"]]
            else:
                proximo_id += 1
                entrada["caso_id"] = f"JS{proximo_id:03d}"

        catalogo.append(entrada)

    elegiveis = [e for e in catalogo if e["elegivel"]]
    print(f"Duplicatas removidas (mesma regra + arquivo): {duplicatas}")
    print(f"Elegiveis apos filtragem: {len(elegiveis)} de {len(catalogo)} (apos dedupe)")

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Catalogo gravado em {SAIDA.relative_to(RAIZ_REPO)}")

    meta = {
        "commit_alvo": commit_alvo,
        "semgrep_versao": versao_semgrep,
        "findings_brutos": findings_brutos,
        "duplicatas_removidas": duplicatas,
        "total_apos_dedup": len(catalogo),
        "elegiveis": len(elegiveis),
        "excluidos": len(catalogo) - len(elegiveis),
        "funil_secao_3": funil(findings),
        "rulesets": RULESETS,
        "exclusoes_caminho": ler_exclusoes(EXCLUSOES),
        "catalogo_anterior": args.catalogo_anterior,
        "casos_mantidos_do_anterior": sorted(e["caso_id"] for e in elegiveis if e["assinatura"] in ids_anteriores),
        "casos_do_anterior_ausentes": sorted(set(ids_anteriores.values())
                                             - {e["caso_id"] for e in elegiveis}),
        "triagem_manual": {k: sum(1 for e in elegiveis if e["triagem_manual"] == k)
                           for k in ("confirmado", "falso_positivo", "inconclusivo", "nao_triado")},
    }
    SAIDA_META.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Metadados gravados em {SAIDA_META.relative_to(RAIZ_REPO)}")


if __name__ == "__main__":
    main()