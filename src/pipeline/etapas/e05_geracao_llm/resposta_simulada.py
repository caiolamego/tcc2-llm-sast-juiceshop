"""Resposta falsa para --dry-run: exercita applier, SAST e validacao sem API."""
from __future__ import annotations

from pathlib import Path

from pipeline.etapas.e05_geracao_llm.esquema import Correcao, Edicao


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


def resposta_falsa_ampliada(issue: dict, wt: Path) -> str | None:
    """Âncora única; apenas JS/TS. Templates são explicitamente não suportados."""
    arquivo = Path(issue['arquivo'])
    if arquivo.suffix.lower() not in {'.ts','.js','.tsx','.jsx'}:
        return None
    content=(wt/arquivo).read_text(encoding='utf-8')
    lines=content.splitlines(keepends=True)
    start=issue['linha_inicio']-1
    for margin in range(3,max(3,len(lines))+1):
        a,b=max(0,start-margin),min(len(lines),issue['linha_fim']+margin)
        original=''.join(lines[a:b])
        if original and content.count(original)==1:
            # Comentário antes da âncora; não adiciona // em expressão/template.
            replacement='// dry-run catalogo ampliado\n'+original
            return Correcao(vulnerabilidade_identificada='[dry-run]',causa_da_vulnerabilidade='[dry-run]',
                estrategia_de_correcao='comentário',edicoes=[Edicao(arquivo=arquivo.as_posix(),trecho_original=original,trecho_corrigido=replacement)],
                justificativa_tecnica='[dry-run]',limitacoes_da_correcao='Sem avaliação de correção real').model_dump_json()
    return None
