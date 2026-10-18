"""Identidade pública e serialização canônica do servidor Colab (sem rede)."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(canonical(data)).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Chave JSON duplicada')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def validar_manifesto(data):
    if not isinstance(data, dict) or set(data) != {'schema_versao', 'cientifica', 'ambiente', 'identidade_sha256'} or data['schema_versao'] != '1.0':
        raise ValueError('Manifesto Colab: schema inválido; exporte novamente pelo notebook atualizado')
    c = data['cientifica']
    required = {'modelo', 'revisao', 'tokenizer', 'tokenizer_revisao', 'chat_template_sha256',
                'quantizacao', 'dtype', 'backend', 'versoes', 'servidor_sha256',
                'contexto_tokens', 'saida_maxima_tokens', 'geracao', 'capacidades'}
    if not isinstance(c, dict) or set(c) != required:
        raise ValueError('Manifesto Colab: identidade científica incompleta')
    for field in ('modelo', 'tokenizer', 'quantizacao', 'dtype', 'backend'):
        if not isinstance(c[field], str) or not c[field].strip() or '<' in c[field]:
            raise ValueError('Manifesto Colab: identidade inválida')
    for field, size in [('revisao', 40), ('tokenizer_revisao', 40), ('chat_template_sha256', 64), ('servidor_sha256', 64)]:
        if not isinstance(c[field], str) or not re.fullmatch('[0-9a-f]{'+str(size)+'}', c[field]):
            raise ValueError('Manifesto Colab: revisão/hash inválido')
    if not isinstance(c['versoes'], dict) or not c['versoes'] or not all(isinstance(v, str) and v for v in c['versoes'].values()):
        raise ValueError('Manifesto Colab: versões ausentes')
    if any(type(c[k]) is not int or c[k] < 1 for k in ('contexto_tokens', 'saida_maxima_tokens')) or c['saida_maxima_tokens'] >= c['contexto_tokens']:
        raise ValueError('Manifesto Colab: limites inválidos')
    if c['geracao'] != {'temperature': 0, 'do_sample': False, 'stream': False} or c['capacidades'] != {'json_schema': True, 'seed': True}:
        raise ValueError('Manifesto Colab: capacidades incompatíveis')
    if not isinstance(data['ambiente'], dict) or not isinstance(data['ambiente'].get('gpu'), str):
        raise ValueError('Manifesto Colab: ambiente ausente')
    if data['identidade_sha256'] != sha(c):
        raise ValueError('Manifesto Colab: hash inconsistente')
    return copy.deepcopy(data)
