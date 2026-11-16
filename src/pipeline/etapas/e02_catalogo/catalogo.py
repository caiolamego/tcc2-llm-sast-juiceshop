"""Carregamento verificável dos catálogos histórico e por ocorrência."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from collections import Counter

from pipeline.comum.caminhos import RAIZ_REPO


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exigir(ok, mensagem):
    if not ok:
        raise ValueError(mensagem)


@dataclass
class Catalogo:
    caminho: Path
    casos: list[dict]
    tipo: str
    commit: str | None
    hashes: dict
    meta: dict

    @property
    def ampliado(self):
        return self.tipo == 'ampliado'


def carregar(caminho: Path) -> Catalogo:
    caminho = caminho.resolve()
    casos = json.loads(caminho.read_text())
    exigir(isinstance(casos, list) and bool(casos), 'Catálogo deve ser lista não vazia')
    exigir(all(isinstance(c, dict) for c in casos), 'Caso inválido')
    ids = [c.get('caso_id') for c in casos]
    exigir(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids), 'IDs inválidos/duplicados')
    hashes = {'catalogo': digest(caminho)}
    if all('assinatura' in c and 'assinatura_ocorrencia' not in c for c in casos):
        meta_path = caminho.with_name('catalogo_meta.json')
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        return Catalogo(caminho, casos, 'historico', meta.get('commit_alvo'), hashes, meta)
    exigir(all('assinatura_ocorrencia' in c and 'assinatura' not in c for c in casos), 'Tipos de caso misturados')
    meta_path, excluded_path = caminho.with_name('catalogo_meta.json'), caminho.with_name('exclusoes.json')
    meta, excluded = json.loads(meta_path.read_text()), json.loads(excluded_path.read_text())
    exigir(meta.get('schema_versao') == '1.0' and meta.get('politica_versao') == 'escopo_apenas_v1', 'Schema/política incompatível')
    exigir(meta.get('catalogo_tipo') == 'ampliado_por_ocorrencia', 'Tipo do catálogo incompatível')
    hashes.update(metadados=digest(meta_path), exclusoes=digest(excluded_path))
    for role, source in meta.get('fontes', {}).items():
        source_path = Path(source['arquivo'])
        exigir(not source_path.is_absolute() and '..' not in source_path.parts, 'Proveniência com caminho inválido')
        stored = RAIZ_REPO / source_path
        exigir(stored.is_file() and digest(stored) == source['sha256'], f'Fonte arquivada ausente/alterada: {role}')
    for file, key in ((caminho.name, 'catalogo'), ('exclusoes.json', 'exclusoes')):
        exigir(meta.get('artefatos', {}).get(file) == hashes[key], f'Hash inválido: {file}')
    counts = meta['contagens']
    exigir(counts['casos_incluidos'] == len(casos) and counts['alertas_excluidos'] == len(excluded)
           and counts['alertas_brutos'] == len(casos) + len(excluded), 'Contagens incompatíveis')
    all_items = casos + excluded
    computed = Counter(c.get('classificacao_auditoria') for c in all_items)
    exigir(computed == Counter({k: v for k, v in counts['por_classificacao'].items() if v}), 'Classificações divergentes')
    sigs = set()
    for c in all_items:
        exigir(c.get('commit_alvo') == meta['commit_alvo'], 'Commit de caso incompatível')
        path = Path(c['arquivo'])
        exigir(not path.is_absolute() and '..' not in path.parts and path.as_posix() == c['arquivo'], 'Caminho de caso inválido')
        coord = [c[k] for k in ('linha_inicio', 'coluna_inicio', 'linha_fim', 'coluna_fim')]
        exigir(all(type(i) is int and i > 0 for i in coord) and tuple(coord[:2]) <= tuple(coord[2:]), 'Coordenadas inválidas')
        raw = [meta['commit_alvo'], c['check_id'], c['arquivo'], *coord]
        sig = hashlib.sha256(json.dumps(raw, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        exigir(sig == c['assinatura_ocorrencia'] and sig not in sigs, 'Assinatura inválida/duplicada')
        sigs.add(sig)
    for c in casos:
        exigir(c.get('elegivel') is True and c['classificacao_auditoria'] in ('confirmado','falso_positivo','inconclusivo'), 'Inclusão incompatível')
        exigir(c['caso_id'] == 'AMP' + c['assinatura_ocorrencia'][:16], 'ID AMP inválido')
    exigir(all(c['classificacao_auditoria'] == 'fora_escopo' for c in excluded), 'Exclusão incompatível')
    return Catalogo(caminho, casos, 'ampliado', meta['commit_alvo'], hashes, meta)
