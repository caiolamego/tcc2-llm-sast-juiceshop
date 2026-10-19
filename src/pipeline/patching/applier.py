"""Âncora exata com fallback conservador de indentação JS/TS (F5.5, D3)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib

from pipeline.patching.indentacao import resolver

VERSAO = "ancora_exata_indentacao_uniforme_js_ts_v2"

from pydantic import ValidationError

from pipeline.llm.schema import Correcao


@dataclass
class ResultadoAplicacao:
    # aplicado | ancora_nao_encontrada | ancora_ambigua | sem_edicoes
    # | fora_de_escopo | json_invalido
    status: str
    arquivos: list[str] = field(default_factory=list)
    detalhe: str = ""
    correspondencias: list[dict] = field(default_factory=list)


PROIBIDOS = ("test/", "node_modules/", "package.json", "package-lock.json")


def interpretar(texto: str | None) -> Correcao | ResultadoAplicacao:
    """Valida a resposta crua contra o schema. Falha vira json_invalido."""
    if not texto:
        return ResultadoAplicacao("json_invalido", [], "resposta vazia ou recusa do modelo")
    try:
        return Correcao.model_validate_json(texto)
    except ValidationError as e:
        return ResultadoAplicacao("json_invalido", [], str(e)[:2000])


def aplicar(wt: Path, correcao: Correcao, *, checkout_parser: Path | None = None) -> ResultadoAplicacao:
    if not correcao.edicoes:
        return ResultadoAplicacao("sem_edicoes", [], "modelo nao devolveu edicoes")

    raiz = wt.resolve()
    # Conteudo em memoria por arquivo: varias edicoes no mesmo arquivo se
    # acumulam (lendo do disco a cada edicao, a segunda apagaria a primeira).
    planejado: dict[Path, str] = {}
    evidencias = []
    for ed in correcao.edicoes:
        rel = ed.arquivo.strip().removeprefix("./")
        if any(rel.startswith(p) for p in PROIBIDOS):
            return ResultadoAplicacao("fora_de_escopo", [], ed.arquivo)

        alvo = (raiz / rel).resolve()
        if not alvo.is_relative_to(raiz) or not alvo.is_file():
            return ResultadoAplicacao("fora_de_escopo", [], ed.arquivo)

        conteudo = planejado.get(alvo)
        if conteudo is None:
            with alvo.open(encoding="utf-8", newline="") as source:
                conteudo = source.read()
        ocorrencias = conteudo.count(ed.trecho_original) if ed.trecho_original else 0
        if ocorrencias == 0:
            result, metodo = resolver(rel, conteudo, ed.trecho_original, ed.trecho_corrigido,
                                      checkout_parser or raiz)
            if result is None:
                status = "ancora_ambigua" if metodo == "ancora_ambigua" else "ancora_nao_encontrada"
                return ResultadoAplicacao(status, [], f"{ed.arquivo}: {metodo}")
            novo, match = result
            evidencias.append({"arquivo":rel,"metodo":metodo,
                               "linha_inicio":match['linha_inicio'],"linha_fim":match['linha_fim'],
                               "deslocamento":list(match['deslocamento']),
                               "ancora_resposta_sha256":hashlib.sha256(ed.trecho_original.encode()).hexdigest(),
                               "ancora_real_sha256":hashlib.sha256(conteudo[match['inicio']:match['fim']].encode()).hexdigest()})
            planejado[alvo] = novo
            continue
        if ocorrencias > 1:
            return ResultadoAplicacao("ancora_ambigua", [], f"{ed.arquivo} ({ocorrencias}x)")

        evidencias.append({"arquivo":rel,"metodo":"exata",
                           "ancora_resposta_sha256":hashlib.sha256(ed.trecho_original.encode()).hexdigest()})
        planejado[alvo] = conteudo.replace(ed.trecho_original, ed.trecho_corrigido, 1)

    # So escreve depois que TODAS as edicoes foram validadas (atomicidade).
    for alvo, novo in planejado.items():
        with alvo.open("w", encoding="utf-8", newline="") as output:
            output.write(novo)

    return ResultadoAplicacao("aplicado", [a.relative_to(raiz).as_posix() for a in planejado],
                              correspondencias=evidencias)
