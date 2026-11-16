"""Classificacao de testes falhos em D (dependem da vulnerabilidade) ou F.

Duas definicoes (analise de sensibilidade, protocolo Secao 13):
- d_marcador: so o criterio (a), assercao de desafio resolvido.
- d_criterio: criterios (a), (b) e (c) de docs/criterios_conjunto_d.md.
A lista vem de config/conjunto_d.json (scripts/gerar_conjunto_d.py). Teste
fora da lista e F. d_marcador esta contido em d_criterio.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from pipeline.caminhos import RAIZ_REPO

ARQ_CONJUNTO_D = RAIZ_REPO / "config" / "conjunto_d.json"


def _padrao_nome(nome: str) -> re.Pattern:
    """Nome do it(...) como regex: partes ${...} (template) viram curinga."""
    partes = re.split(r"\$\{[^}]*\}", nome)
    return re.compile("^" + ".+".join(re.escape(p) for p in partes) + "$")


@lru_cache(maxsize=1)
def _lista() -> tuple[list[tuple[str, re.Pattern, str]], str]:
    dados = json.loads(ARQ_CONJUNTO_D.read_text(encoding="utf-8"))
    itens = [(d["arquivo"], _padrao_nome(d["nome"]), d["criterio"]) for d in dados["d"]]
    return itens, dados.get("gerado_em", "")


def criterio_de(teste: str) -> str | None:
    """'a', 'b', 'c' ou None (F). teste = '<arquivo> :: <suite> > ... > <nome>'."""
    arquivo, _, caminho = teste.partition(" :: ")
    nome = caminho.split(" > ")[-1]
    for arq, padrao, crit in _lista()[0]:
        if arq == arquivo and padrao.match(nome):
            return crit
    return None


def classificar(testes: list[str]) -> dict[str, list[str]]:
    """Separa testes falhos nas duas definicoes de D e nos F correspondentes."""
    crit = {t: criterio_de(t) for t in testes}
    d_marcador = sorted(t for t, c in crit.items() if c == "a")
    d_criterio = sorted(t for t, c in crit.items() if c is not None)
    return {
        "d_marcador": d_marcador,
        "d_criterio": d_criterio,
        "f_marcador": sorted(set(testes) - set(d_marcador)),
        "f_criterio": sorted(set(testes) - set(d_criterio)),
    }
