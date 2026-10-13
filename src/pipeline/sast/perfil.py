"""Perfil local de regras, sem acesso ao registro remoto durante a execução."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import fnmatch
import json
import hashlib
import yaml
from pipeline.catalogo import digest, exigir


@dataclass
class Perfil:
    caminho: Path
    dados: dict
    hash: str

    @property
    def configs(self):
        return [self.caminho.parent / c['arquivo'] for c in self.dados['configs']]

    def no_escopo(self, path: str) -> bool:
        for pattern in self.dados['escopo']:
            if pattern.endswith('/'):
                part = pattern.rstrip('/')
                if path.startswith(part + '/') or '/' + part + '/' in '/' + path:
                    return False
            elif fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern):
                return False
        return True

    def conferir(self):
        exigir(digest(self.caminho) == self.hash, 'Manifesto do perfil alterado')
        for config in self.dados['configs']:
            exigir(digest(self.caminho.parent / config['arquivo']) == config['sha256'], 'Regras congeladas alteradas')


def carregar(path: Path) -> Perfil:
    path = path.resolve()
    d = json.loads(path.read_text())
    exigir(d.get('schema_versao') == '1.0' and d.get('semgrep_versao') == '1.177.0', 'Schema/versão do perfil incompatível')
    exigir(d.get('flags') == {'metrics': 'off', 'rewrite_rule_ids': False, 'use_git_ignore': True}, 'Flags incompatíveis')
    exigir(isinstance(d.get('escopo'), list) and all(isinstance(x,str) for x in d['escopo']), 'Escopo inválido')
    exigir(d.get('escopo_sha256') == hashlib.sha256(json.dumps(d['escopo'],ensure_ascii=False,separators=(',',':')).encode()).hexdigest(), 'Hash do escopo inválido')
    exigir(d.get('timeout_regra_s') == 30 and d.get('timeout_processo_s') == 900, 'Timeouts incompatíveis')
    configs = d.get('configs', [])
    exigir(len(configs) == 2, 'Perfil requer duas configurações locais')
    actual = []
    for item in configs:
        p = Path(item['arquivo'])
        exigir(not p.is_absolute() and '..' not in p.parts, 'Caminho de regra inválido')
        exigir(digest(path.parent / p) == item['sha256'], 'Hash de regra inválido')
        rules = yaml.safe_load((path.parent / p).read_text())['rules']
        actual.extend(r['id'] for r in rules)
    exigir(len(set(actual)) == len(actual) and sorted(actual) == d['id_regras'], 'IDs duplicados/divergentes')
    return Perfil(path, d, digest(path))
