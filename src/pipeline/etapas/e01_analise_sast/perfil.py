"""Perfil local de regras, sem acesso ao registro remoto durante a execução."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import fnmatch
import json
import hashlib
import yaml
from pipeline.etapas.e02_catalogo.catalogo import digest, exigir


def bytes_regras(path: Path) -> bytes:
    """Verifica a sanitização reversível de exemplos em snapshots históricos."""
    path = Path(path)
    raw = path.read_bytes()
    sidecar = path.with_suffix(path.suffix + '.sanitizacao.json')
    if not sidecar.exists():
        return raw
    meta = json.loads(sidecar.read_text())
    exigir(meta.get('schema_versao') == '1.0', 'Sanitização incompatível')
    exigir(hashlib.sha256(raw).hexdigest() == meta['sha256_sanitizado'], 'Snapshot sanitizado alterado')
    # Somente o domínio do exemplo Slack pode ser transformado.
    exigir(meta.get('substituicao') == {
        'original': 'https://hooks.slack.com/',
        'sanitizado': 'https://hooks.slack.example.invalid/',
        'ocorrencias': 1,
    }, 'Transformação de sanitização inválida')
    exigir(raw.count(b'https://hooks.slack.example.invalid/') == 1, 'Exemplo sanitizado divergente')
    original = raw.replace(b'https://hooks.slack.example.invalid/', b'https://hooks.slack.com/')
    exigir(hashlib.sha256(original).hexdigest() == meta['sha256_original'], 'Hash histórico divergente')
    return original


def digest_regras(path: Path) -> str:
    return hashlib.sha256(bytes_regras(path)).hexdigest()


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
            exigir(digest_regras(self.caminho.parent / config['arquivo']) == config['sha256'], 'Regras congeladas alteradas')


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
        exigir(digest_regras(path.parent / p) == item['sha256'], 'Hash de regra inválido')
        rules = yaml.safe_load(bytes_regras(path.parent / p).decode('utf-8'))['rules']
        actual.extend(r['id'] for r in rules)
    exigir(len(set(actual)) == len(actual) and sorted(actual) == d['id_regras'], 'IDs duplicados/divergentes')
    return Perfil(path, d, digest(path))
