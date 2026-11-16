"""Seleção revisada de testes; lacunas produzem fallback amplo."""
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
import yaml


class YAMLUnico(yaml.SafeLoader):
    pass


def _map(loader, node):
    result = {}
    for key, value in node.value:
        k = loader.construct_object(key)
        if k in result:
            raise ValueError(f'Chave YAML duplicada: {k}')
        result[k] = loader.construct_object(value)
    return result


YAMLUnico.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _map)


def interno(wt, nome):
    if not isinstance(nome,str):
        raise ValueError('Caminho deve ser texto')
    p = PurePosixPath(nome)
    if not isinstance(nome, str) or p.is_absolute() or '..' in p.parts or not nome:
        raise ValueError('Caminho inválido no mapa de testes')
    path = (wt / nome).resolve()
    if not path.is_relative_to(wt.resolve()):
        raise ValueError('Teste fora da worktree')
    return path


@dataclass
class Selecao:
    unitarios: list[str]
    api: list[str]
    fallback: bool
    motivos: list[str]
    arquivos: list[str]

    def to_dict(self):
        return asdict(self)


def selecionar(mapa: Path, wt: Path, arquivos):
    try:
        dados = yaml.load(mapa.read_text(encoding='utf-8'), Loader=YAMLUnico)
    except yaml.YAMLError as exc:
        raise ValueError('YAML de testes inválido') from exc
    if not isinstance(dados, dict) or dados.get('schema_versao') != '1.0' or not isinstance(dados.get('arquivos'), dict):
        raise ValueError('Schema do mapa de testes inválido')
    for origem, regra in dados['arquivos'].items():
        interno(wt, origem)
        if not isinstance(regra, dict) or regra.get('modo') not in ('relacionados', 'amplo') or not regra.get('justificativa'):
            raise ValueError(f'Associação inválida: {origem}')
        for tipo, prefixo, sufixo in (('unitarios', 'test/server/', '.unit.test.ts'), ('api', 'test/api/', '.test.ts')):
            testes = regra.get(tipo, [])
            if not isinstance(testes, list) or any(not isinstance(t,str) for t in testes) or len(set(testes)) != len(testes):
                raise ValueError('Lista de testes inválida/duplicada')
            for teste in testes:
                if not teste.startswith(prefixo) or not teste.endswith(sufixo) or not interno(wt, teste).is_file():
                    raise ValueError(f'Teste inválido/ausente: {teste}')
    unitarios, api, motivos = set(), set(), []
    for arquivo in sorted(set(arquivos)):
        interno(wt, arquivo)
        regra = dados['arquivos'].get(arquivo)
        if not regra or regra['modo'] == 'amplo':
            motivos.append(f'{arquivo}: ' + (regra['justificativa'] if regra else 'arquivo não mapeado'))
        else:
            unitarios.update(regra.get('unitarios', []))
            api.update(regra.get('api', []))
            if not regra.get('unitarios') and not regra.get('api'):
                motivos.append(f'{arquivo}: seleção vazia')
    if not arquivos:
        motivos.append('sem arquivos alterados')
    return Selecao(sorted(unitarios), sorted(api), bool(motivos), motivos, sorted(set(arquivos)))
