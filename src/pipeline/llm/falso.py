"""Resposta falsa para --dry-run: exercita applier, SAST e validacao sem API."""
from __future__ import annotations

from pathlib import Path

from pipeline.llm.schema import Correcao, Edicao


def resposta_falsa(issue: dict, wt: Path) -> str:
    """Edicao inofensiva: acrescenta um comentario no fim da linha do finding."""
    linhas = (Path(wt) / issue["arquivo"]).read_text(encoding="utf-8").splitlines()
    linha = linhas[issue["linha_inicio"] - 1]
    c = Correcao(
        vulnerabilidade_identificada="[dry-run]",
        causa_da_vulnerabilidade="[dry-run]",
        estrategia_de_correcao="[dry-run] comentario inofensivo",
        edicoes=[Edicao(arquivo=issue["arquivo"], trecho_original=linha,
                        trecho_corrigido=linha + " // dry-run")],
        justificativa_tecnica="[dry-run]",
        limitacoes_da_correcao="[dry-run]",
    )
    return c.model_dump_json()
