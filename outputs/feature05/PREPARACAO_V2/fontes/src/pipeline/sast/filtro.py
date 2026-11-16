"""Filtro de elegibilidade do protocolo (Secao 3, passos 2-4).

Usado pelo catalogo (scripts/build_issue_catalog.py) e pelo criterio M da
F6, para que "alerta de seguranca" signifique a mesma coisa nos dois lugares.
"""
from __future__ import annotations

from pipeline.sast.semgrep_client import Finding

SEVERIDADES_ACEITAS = {
    # Legado (regras mais antigas): ERROR = HIGH, WARNING = MEDIUM, INFO = LOW.
    # Atual (regras migradas): CRITICAL, HIGH, MEDIUM, LOW.
    # Os dois esquemas coexistem na mesma execucao -- confirmado em F3.4
    # (dois findings vieram com severidade "MEDIUM"). Excluimos so o nivel
    # mais baixo em qualquer esquema (INFO / LOW), mantendo a intencao
    # original do D1 ("ERROR e WARNING") sob os dois nomes possiveis.
    "ERROR", "WARNING", "CRITICAL", "HIGH", "MEDIUM",
}


def filtrar(f: Finding) -> tuple[bool, str | None]:
    """Passos 2-4 do protocolo D1. Retorna (elegivel, motivo_exclusao)."""
    if f.category != "security":
        return False, f"categoria '{f.category}' != security"
    if f.severity not in SEVERIDADES_ACEITAS:
        return False, f"severidade '{f.severity}' fora de {sorted(SEVERIDADES_ACEITAS)}"
    if not f.cwe:
        return False, "sem CWE mapeada"
    return True, None
