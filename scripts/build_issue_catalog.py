#!/usr/bin/env python3
"""Constroi o catalogo de issues elegiveis a partir do baseline SAST (F3.2),
aplicando o protocolo de filtragem deterministico da Decisao D1. Roda uma
unica vez por execucao do baseline -- NAO chama o semgrep de novo, so le o
JSON ja gerado. Grava outputs/sast_antes/catalogo_issues.json com TODOS os
findings (elegiveis e excluidos, cada um com o motivo), para auditoria.

Uso:
    python scripts/build_issue_catalog.py [--worktree workspace/wt-1]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

RAIZ_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_REPO / "src"))
from pipeline.sast.semgrep_client import carregar_resultados, assinatura, Finding  # noqa: E402

BASELINE_JSON = RAIZ_REPO / "outputs" / "sast_antes" / "baseline_raw.json"
SAIDA = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_issues.json"

MAPA_CWE = RAIZ_REPO / "config" / "mapa_cwe_vuln.yaml"
MAPA_OWASP = RAIZ_REPO / "config" / "mapa_owasp.yaml"
MAPA_RAG = RAIZ_REPO / "config" / "mapa_categoria_rag.yaml"

SEVERIDADES_ACEITAS = {
    # Legado (regras mais antigas): ERROR = HIGH, WARNING = MEDIUM, INFO = LOW.
    # Atual (regras migradas): CRITICAL, HIGH, MEDIUM, LOW.
    # Os dois esquemas coexistem na mesma execucao -- confirmado em F3.4
    # (dois findings vieram com severidade "MEDIUM"). Excluimos so o nivel
    # mais baixo em qualquer esquema (INFO / LOW), mantendo a intencao
    # original do D1 ("ERROR e WARNING") sob os dois nomes possiveis.
    "ERROR", "WARNING", "CRITICAL", "HIGH", "MEDIUM",
}
LIMITE_ARQUIVO_COMPLETO = 250  # linhas -- ver Decisao D3


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


def filtrar(f: Finding) -> tuple[bool, str | None]:
    """Passos 2-4 do protocolo D1. Retorna (elegivel, motivo_exclusao)."""
    if f.category != "security":
        return False, f"categoria '{f.category}' != security"
    if f.severity not in SEVERIDADES_ACEITAS:
        return False, f"severidade '{f.severity}' fora de {sorted(SEVERIDADES_ACEITAS)}"
    if not f.cwe:
        return False, "sem CWE mapeada"
    return True, None


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", default="workspace/wt-1")
    args = ap.parse_args()
    worktree = (RAIZ_REPO / args.worktree).resolve()

    mapa_cwe = carregar_yaml(MAPA_CWE)
    mapa_owasp = carregar_yaml(MAPA_OWASP)
    mapa_rag = carregar_yaml(MAPA_RAG)

    if not BASELINE_JSON.exists():
        raise SystemExit(f"Baseline nao encontrado: {BASELINE_JSON}. Rode F3.2 primeiro.")

    findings = carregar_resultados(BASELINE_JSON, worktree)
    print(f"Findings brutos carregados: {len(findings)}")

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

        if elegivel:
            total_linhas, modo_contexto = contexto_do_arquivo(worktree, f.path)
        else:
            total_linhas, modo_contexto = None, None

        entrada = {
            "caso_id": None,
            "assinatura": assinatura(f),
            "check_id": f.check_id,
            "arquivo": f.path,
            "linha_inicio": f.start_line,
            "linha_fim": f.end_line,
            "severidade": f.severity,
            "mensagem": f.message,
            "cwe": list(f.cwe),
            "owasp_2021": list(f.owasp),
            "owasp_2025": owasp_2025,
            "sigla_vuln": sigla_vuln,
            "categoria_rag": categoria_rag,
            "trecho": f.code,
            "linhas_arquivo": total_linhas,
            "modo_contexto": modo_contexto,
            "marcador_juiceshop": None,   # preenchido em F3.5
            "elegivel": elegivel,
            "motivo_exclusao": motivo,
        }

        if elegivel:
            contador += 1
            entrada["caso_id"] = f"JS{contador:03d}"

        catalogo.append(entrada)

    elegiveis = [e for e in catalogo if e["elegivel"]]
    print(f"Duplicatas removidas (mesma regra + arquivo): {duplicatas}")
    print(f"Elegiveis apos filtragem: {len(elegiveis)} de {len(catalogo)} (apos dedupe)")

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Catalogo gravado em {SAIDA}")


if __name__ == "__main__":
    main()