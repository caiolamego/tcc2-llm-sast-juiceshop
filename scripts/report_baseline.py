#!/usr/bin/env python3
"""Gera o relatorio do baseline SAST (F3.6) a partir do catalogo ja
filtrado (F3.4) e cruzado com marcadores (F3.5). Imprime no terminal E
grava em outputs/sast_antes/relatorio_baseline.md, pronto para colar no
caderno de laboratorio.

Uso:
    python scripts/report_baseline.py
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parent.parent
CATALOGO = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_issues.json"
META = RAIZ_REPO / "outputs" / "sast_antes" / "catalogo_meta.json"
SAIDA_MD = RAIZ_REPO / "outputs" / "sast_antes" / "relatorio_baseline.md"


def cwe_codigo(cwe_lista: list[str]) -> str | None:
    """So o primeiro CWE de cada finding -- findings com 2+ CWEs (ex.: os
    da sigla INTEGRITY) so contam sob o primeiro. Mesmo criterio usado em
    build_issue_catalog.py para resolver sigla_vuln (consistente, mas
    significa que a segunda CWE de um finding multiplo nunca aparece
    sozinha nesta contagem)."""
    if not cwe_lista:
        return None
    m = re.match(r"(CWE-\d+)", cwe_lista[0])
    return m.group(1) if m else cwe_lista[0]


def eh_codigo_aplicacao(arquivo: str) -> bool:
    """Heuristica simples para sinalizar findings fora do escopo do
    experimento (config de CI/CD, gerenciador de pacotes) -- nenhum dos
    dois e testavel pela suite automatizada do Juice Shop nem faz sentido
    no fluxo de correcao via LLM + reteste. Ver caderno, F3.6."""
    return not (arquivo.startswith(".github/") or arquivo.endswith(".npmrc"))


def main() -> None:
    if not CATALOGO.exists():
        raise SystemExit(f"Catalogo nao encontrado: {CATALOGO}. Rode F3.4 primeiro.")

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    elegiveis = [e for e in catalogo if e["elegivel"]]
    excluidos = [e for e in catalogo if not e["elegivel"]]

    if META.exists():
        meta = json.loads(META.read_text(encoding="utf-8"))
        linha_brutos = (
            f"- Findings brutos (Semgrep, apos exclusao de caminhos em D1): {meta['findings_brutos']}\n"
            f"- Duplicatas removidas (mesma regra + arquivo): {meta['duplicatas_removidas']}\n"
            f"- Total apos deduplicacao: {meta['total_apos_dedup']}"
        )
    else:
        # Catalogo antigo, gerado antes de F3.6 persistir os metadados --
        # len(catalogo) aqui e o total POS-dedupe, nao o bruto. Rode
        # build_issue_catalog.py de novo para ter o numero bruto real.
        linha_brutos = (
            f"- Total no catalogo (apos deduplicacao -- catalogo_meta.json "
            f"nao encontrado, numero bruto pre-dedupe indisponivel): {len(catalogo)}"
        )

    nao_aplicacao = [e for e in elegiveis if not eh_codigo_aplicacao(e["arquivo"])]

    por_severidade = Counter(e["severidade"] for e in elegiveis)
    por_severidade_norm = Counter(e.get("severidade_normalizada") for e in elegiveis)
    por_sigla = Counter(e["sigla_vuln"] for e in elegiveis)
    por_cwe = Counter(cwe_codigo(e["cwe"]) for e in elegiveis)
    por_owasp = Counter(e["owasp_2025"] for e in elegiveis)
    por_arquivo = Counter(e["arquivo"] for e in elegiveis)
    por_motivo_exclusao = Counter(e["motivo_exclusao"] for e in excluidos)
    com_marcador = sum(1 for e in elegiveis if e.get("marcador_juiceshop"))

    linhas = [
        "# Relatorio do baseline SAST\n",
        linha_brutos,
        f"- Elegiveis apos protocolo de filtragem (D1): {len(elegiveis)}",
        f"- Excluidos: {len(excluidos)}",
        f"- Elegiveis com marcador vuln-code-snippet (ground truth parcial, F3.5): {com_marcador} de {len(elegiveis)}",
        f"- **Fora do codigo de aplicacao (CI/CD, .npmrc etc. -- revisar escopo, ver caderno): {len(nao_aplicacao)} de {len(elegiveis)}**\n",
        "## Por severidade (bruta, como reportada pelo Semgrep)\n",
        *[f"- {s}: {q}" for s, q in por_severidade.most_common()],
        "\n## Por severidade (normalizada -- ALTA = ERROR/HIGH/CRITICAL, MEDIA = WARNING/MEDIUM)\n",
        *[f"- {s}: {q}" for s, q in por_severidade_norm.most_common()],
        "\n## Por CWE (primeira CWE de cada finding -- ver nota na funcao cwe_codigo)\n",
        *[f"- {c or '(sem CWE)'}: {q}" for c, q in por_cwe.most_common()],
        "\n## Por sigla de vulnerabilidade\n",
        *[f"- {s}: {q}" for s, q in por_sigla.most_common()],
        "\n## Por categoria OWASP 2025\n",
        *[f"- {o or '(sem mapeamento)'}: {q}" for o, q in por_owasp.most_common()],
        "\n## Top 10 arquivos com mais findings\n",
        *[f"- {a}: {q}" for a, q in por_arquivo.most_common(10)],
    ]
    if excluidos:
        linhas += ["\n## Motivos de exclusao\n",
                   *[f"- {m}: {q}" for m, q in por_motivo_exclusao.most_common()]]
    if nao_aplicacao:
        linhas += ["\n## Findings fora do codigo de aplicacao (revisar escopo)\n",
                   *[f"- {e['caso_id']} {e['arquivo']} ({e['sigla_vuln']})" for e in nao_aplicacao]]

    texto = "\n".join(linhas) + "\n"
    print(texto)
    SAIDA_MD.write_text(texto, encoding="utf-8")
    print(f"\nRelatorio gravado em {SAIDA_MD}")


if __name__ == "__main__":
    main()