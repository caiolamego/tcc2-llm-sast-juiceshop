"""RAG por categoria: validação integral sem rede, cache ou escrita implícita."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse

import yaml
from pipeline.comum.caminhos import RAIZ_REPO

CATEGORIAS = ('injection','broken_access_control','cryptographic_failures','cross_site_scripting',
              'security_misconfiguration','authentication_failures','input_validation',
              'integrity_failures','concurrency','generico')
SECOES = ('Descrição e sinais','Origem e condições','Impactos e interpretação','Mitigação por mecanismo',
          'Preservação funcional','Exemplo genérico','Limitações e verificação')


class BaseInvalida(ValueError):
    pass


def exigir(ok, message):
    if not ok:
        raise BaseInvalida(message)


def sha(raw: bytes):
    return hashlib.sha256(raw).hexdigest()


class LoaderUnico(yaml.SafeLoader):
    pass


def _mapping(loader, node):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        exigir(isinstance(key, str) and key not in result, 'Chave YAML inválida ou duplicada')
        result[key] = loader.construct_object(value_node, deep=True)
    return result


LoaderUnico.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def ler_yaml(text):
    try:
        return yaml.load(text, Loader=LoaderUnico)
    except yaml.YAMLError as exc:
        raise BaseInvalida(f'YAML inválido: {exc}') from exc


def serializar(data):
    return (json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')


def caminho_local(base, name):
    exigir(isinstance(name,str) and bool(name), 'Nome de arquivo inválido')
    p = Path(name)
    exigir(not p.is_absolute() and '..' not in p.parts, 'Caminho externo na base')
    resolved = (base/p).resolve()
    exigir(resolved.is_relative_to(base.resolve()) and resolved.is_file(), f'Arquivo ausente ou fora da base: {name}')
    return resolved


def ler_documento(path: Path, categoria):
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    m = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n', text, re.S)
    exigir(m is not None, f'{path.name}: frontmatter obrigatório')
    meta, body = ler_yaml(m.group(1)), text[m.end():]
    exigir(isinstance(meta,dict), f'{path.name}: metadados inválidos')
    exigir(meta.get('schema_versao') == '1.0' and meta.get('categoria') == categoria, f'{path.name}: schema/categoria inválida')
    exigir(meta.get('status') == 'PRONTO', f'{path.name}: documento não está PRONTO')
    exigir(isinstance(meta.get('versao_documento'),str) and re.fullmatch(r'\d+\.\d+(?:\.\d+)?',meta['versao_documento']), 'Versão do documento inválida')
    sources=meta.get('fontes')
    exigir(isinstance(sources,list) and bool(sources), 'Fontes obrigatórias')
    for source in sources:
        exigir(isinstance(source,dict) and all(isinstance(source.get(k),str) and source[k].strip() for k in ('titulo','url','consultado_em')), 'Fonte inválida')
        u=urlparse(source['url'])
        exigir(u.scheme=='https' and bool(u.netloc) and u.username is None and u.password is None, 'URL da fonte inválida')
        try: date.fromisoformat(source['consultado_em'])
        except ValueError as exc: raise BaseInvalida('Data de consulta inválida') from exc
    exigir(bool(body.strip()) and len(body)<=20000, f'{path.name}: corpo vazio ou maior que 20.000 caracteres')
    positions=[body.find(f'## {i}. {heading}') for i,heading in enumerate(SECOES,1)]
    exigir(all(p>=0 for p in positions) and positions==sorted(positions), f'{path.name}: sete seções obrigatórias, em ordem')
    exigir(body.count('```')>=4, f'{path.name}: exemplos vulnerável e corrigido obrigatórios')
    return {'categoria':categoria,'versao_documento':meta['versao_documento'],'fontes':sources,
            'documento_sha256':sha(raw),'corpo_sha256':sha(body.encode('utf-8'))}, body


@dataclass
class Base:
    diretorio: Path
    indice: dict
    manifesto: dict
    corpos: dict[str,str]
    hash_base: str


def inspecionar(base: Path):
    base=base.resolve()
    index_path=caminho_local(base,'_index.yaml')
    index_raw=index_path.read_bytes()
    idx=ler_yaml(index_raw.decode('utf-8'))
    exigir(isinstance(idx,dict) and idx.get('schema_versao')=='1.0', 'Schema do índice inválido')
    exigir(isinstance(idx.get('base_versao'),str) and re.fullmatch(r'\d+\.\d+(?:\.\d+)?',idx['base_versao']), 'Versão da base inválida')
    docs=idx.get('documentos');cwes=idx.get('cwe')
    exigir(isinstance(docs,dict) and set(docs)==set(CATEGORIAS), 'Índice deve declarar as dez categorias')
    exigir(idx.get('fallback')=='generico', 'Fallback deve ser generico')
    exigir(all(isinstance(v,str) and v for v in docs.values()), 'Arquivos do índice inválidos')
    exigir(isinstance(cwes,dict) and all(re.fullmatch(r'CWE-\d+',k) and isinstance(v,str) and v in docs for k,v in cwes.items()), 'Mapeamento CWE inválido')
    exigir(len(set(docs.values()))==len(docs), 'Categorias não podem compartilhar arquivo')
    document_meta, bodies = {}, {}
    for cat,name in sorted(docs.items()):
        path=caminho_local(base,name)
        meta,body=ler_documento(path,cat)
        document_meta[cat]={'arquivo':name,**meta}
        bodies[cat]=body
    manifest={'schema_versao':'1.0','base_versao':idx['base_versao'],
              'index_sha256':sha(index_raw),'documentos':document_meta}
    return idx,manifest,bodies


def carregar_base(base: Path) -> Base:
    try:
        idx,expected,bodies=inspecionar(base)
        manifest_path=caminho_local(base,'manifesto.json')
        raw=manifest_path.read_bytes()
        actual=json.loads(raw)
        exigir(actual==expected,'Manifesto diverge do índice/documentos; nova versão é necessária')
        return Base(base.resolve(),idx,actual,bodies,sha(raw))
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise BaseInvalida(f'Base indisponível/inválida: {exc}') from exc


def publicar_manifesto(base: Path):
    _,manifest,_=inspecionar(base)
    path=base/'manifesto.json'
    # Escrita exclusiva: nunca substituir uma base congelada.
    with path.open('xb') as f:
        try:
            f.write(serializar(manifest))
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    return manifest


@dataclass
class Recuperacao:
    categoria: str
    arquivo: str
    versao: str
    corpo: str
    documento_sha256: str
    corpo_sha256: str
    index_sha256: str
    base_sha256: str
    motivo: str
    cwe: str | None


def recuperar(issue: dict, base: Path) -> Recuperacao:
    published=carregar_base(base)
    ids=issue.get('cwe_ids')
    if ids is None:
        raw=issue.get('cwe') or []
        if isinstance(raw,str): raw=[raw]
        exigir(isinstance(raw,list), 'Lista CWE histórica inválida')
        ids=[m.group(0) for text in raw if isinstance(text,str) and (m:=re.match(r'CWE-\d+\b',text))]
    exigir(isinstance(ids,list) and all(isinstance(k,str) for k in ids),'CWEs do caso inválidas')
    cwe=next((k for k in ids if k in published.indice['cwe']),None)
    category=issue.get('categoria_rag')
    if cwe:
        category=published.indice['cwe'][cwe];reason='cwe'
    elif isinstance(category,str) and category in published.indice['documentos']:
        reason='categoria_catalogo'
    else:
        category=published.indice['fallback'];reason='fallback'
    meta=published.manifesto['documentos'][category]
    path=published.diretorio/meta['arquivo']
    try: name=path.relative_to(RAIZ_REPO).as_posix()
    except ValueError: name='knowledge_base/'+meta['arquivo']
    return Recuperacao(category,name,meta['versao_documento'],published.corpos[category],
          meta['documento_sha256'],meta['corpo_sha256'],published.manifesto['index_sha256'],published.hash_base,reason,cwe)
