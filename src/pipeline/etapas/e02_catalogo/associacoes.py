"""Sobreposição documental separada do catálogo científico congelado."""
import hashlib
from pathlib import Path
import yaml

TIPOS = {'mecanismos_distintos', 'sem_referencia', 'referencia_em_outro_arquivo',
         'fora_do_trecho', 'montagem_ambigua'}


class Loader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    pairs = loader.construct_pairs(node, deep=deep)
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Chave duplicada nas revisões')
        result[key] = value
    return result


Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def carregar(path, catalogo_path, casos, raiz):
    data = yaml.load(Path(path).read_text(encoding='utf-8'), Loader=Loader)
    if not isinstance(data, dict) or data.get('schema_versao') != '1.0':
        raise ValueError('Schema de revisões inválido')
    if data.get('catalogo_sha256') != hashlib.sha256(Path(catalogo_path).read_bytes()).hexdigest():
        raise ValueError('Catálogo divergente das revisões')
    ids, seen = {c['caso_id'] for c in casos}, set()
    if not isinstance(data.get('revisoes'), list):
        raise ValueError('Lista de revisões ausente')
    for row in data['revisoes']:
        if not isinstance(row, dict):
            raise ValueError('Revisão deve ser um objeto')
        case = row.get('caso_id')
        if case not in ids or case in seen or row.get('tipo') not in TIPOS:
            raise ValueError('Caso/tipo de revisão inválido ou duplicado')
        seen.add(case)
        if not isinstance(row.get('conclusao'), str) or not row['conclusao'].strip():
            raise ValueError('Conclusão ausente')
        if row.get('desafio') is not None and not isinstance(row['desafio'], str):
            raise ValueError('Desafio inválido')
        evidence = Path(row.get('evidencia', ''))
        local = (Path(raiz)/evidence).resolve()
        if evidence.is_absolute() or '..' in evidence.parts or not local.is_relative_to(Path(raiz).resolve()) or not local.exists():
            raise ValueError('Evidência ausente ou externa')
    return data
