"""Caminhos relativos a raiz do repositorio, para os JSON de resultado
nao carregarem /Users/<pessoa>/... (portabilidade e anonimato)."""
from __future__ import annotations

from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[3]


def rel(caminho: Path | str) -> str:
    """Caminho relativo a raiz do repo (inalterado se estiver fora dela)."""
    p = Path(caminho).resolve()
    try:
        return p.relative_to(RAIZ_REPO).as_posix()
    except ValueError:
        return str(caminho)


def relativizar_texto(texto: str, base: Path | None = None) -> str:
    """Remove o prefixo absoluto de 'base' (ou da raiz do repo) de um texto
    livre, como a saida de um teste com stack trace."""
    raiz = str((base or RAIZ_REPO).resolve())
    return texto.replace(raiz + "/", "").replace(raiz, ".")
