"""Métricas offline: contratos e resultados, sem executar o experimento."""
import hashlib
import json
from pathlib import Path

VERSAO = '1.0'


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pares(pares):
    result = {}
    for key, value in pares:
        exigir(key not in result, f'Chave JSON duplicada: {key}')
        result[key] = value
    return result


def ler_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_pares,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f'Número JSON inválido: {x}')))


def relativo(raiz, nome, existe=True):
    exigir(isinstance(nome, str) and bool(nome), 'Caminho inválido')
    path = Path(nome)
    exigir(not path.is_absolute() and '..' not in path.parts and '\\' not in nome, 'Caminho externo/inválido')
    result = (raiz/path).resolve()
    exigir(result.is_relative_to(raiz.resolve()), 'Symlink externo')
    exigir(not existe or result.is_file(), f'Artefato ausente: {nome}')
    return result
