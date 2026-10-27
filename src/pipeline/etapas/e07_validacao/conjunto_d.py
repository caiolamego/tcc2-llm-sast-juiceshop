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

from pipeline.comum.caminhos import RAIZ_REPO

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


def criterio_de(teste: str, conjunto=None) -> str | None:
    """'a', 'b', 'c' ou None (F). teste = '<arquivo> :: <suite> > ... > <nome>'."""
    arquivo, _, caminho = teste.partition(" :: ")
    nome = caminho.split(" > ")[-1]
    itens=_lista()[0] if conjunto is None else _carregar_versionado(conjunto)
    for arq, padrao, crit in itens:
        if arq == arquivo and padrao.match(nome):
            return crit
    return None


def _carregar_versionado(arquivo):
    from pathlib import Path
    data=json.loads(Path(arquivo).read_text(encoding='utf-8'))
    if data.get('schema_versao')!='2.0' or not isinstance(data.get('d'),list):
        raise ValueError('Conjunto D versionado inválido')
    seen=set();items=[]
    for row in data['d']:
        key=(row['arquivo'],row['nome'])
        if key in seen or row['criterio'] not in ('a','b','c'):raise ValueError('Classificação D inválida/duplicada')
        seen.add(key);items.append((row['arquivo'],_padrao_nome(row['nome']),row['criterio']))
    return items


def classificar(testes: list[str], arquivo=None) -> dict[str, list[str]]:
    """Separa testes falhos nas duas definicoes de D e nos F correspondentes."""
    crit = {t: criterio_de(t,arquivo) for t in testes}
    d_marcador = sorted(t for t, c in crit.items() if c == "a")
    d_criterio = sorted(t for t, c in crit.items() if c is not None)
    return {
        "d_marcador": d_marcador,
        "d_criterio": d_criterio,
        "f_marcador": sorted(set(testes) - set(d_marcador)),
        "f_criterio": sorted(set(testes) - set(d_criterio)),
    }
