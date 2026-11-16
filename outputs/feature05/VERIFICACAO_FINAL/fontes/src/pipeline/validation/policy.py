"""Opções públicas e identidade científica da validação."""
from pathlib import Path
from pipeline.caminhos import RAIZ_REPO

DEFAULTS = {'politica_validacao': 'historica_v1', 'mapa_testes': None,
            'cache_validacao': 'desligado', 'repeticao_api': 'ampla'}
CHOICES = {'politica_validacao': ('historica_v1', 'otimizada_v1'),
           'cache_validacao': ('desligado', 'leitura', 'leitura-escrita'),
           'repeticao_api': ('ampla', 'seletiva-experimental')}


def argumentos(parser):
    for nome, padrao in DEFAULTS.items():
        kwargs = {'default': padrao}
        if nome in CHOICES:
            kwargs['choices'] = CHOICES[nome]
        else:
            kwargs['type'] = Path
        parser.add_argument('--' + nome.replace('_', '-'), **kwargs)


def opcoes(args):
    valores = {k: getattr(args, k, v) for k, v in DEFAULTS.items()}
    for k, choices in CHOICES.items():
        if valores[k] not in choices:
            raise ValueError(f'{k} inválido')
    mapa = valores['mapa_testes']
    if valores['politica_validacao'] == 'otimizada_v1' and not mapa:
        raise ValueError('Política otimizada requer --mapa-testes')
    if mapa:
        valores['mapa_testes'] = Path(mapa).resolve()
    return valores


def alterada(args):
    return any(v != DEFAULTS[k] for k, v in opcoes(args).items())


def identidade(args, worktrees):
    from pipeline.validation.identity import digest, hash_json, ambiente
    valores = opcoes(args)
    mapa = valores.pop('mapa_testes')
    valores['mapa_testes_sha256'] = digest(mapa) if mapa else None
    from pipeline.validation.components import componentes
    valores['implementacao'] = componentes()
    ambientes = []
    for wt in (() if getattr(args,'somente_preflight',False) else worktrees):
        if (wt / 'node_modules').is_dir():
            env = ambiente(wt)
            env.pop('porta_api')  # Porta do slot é operacional; a evidência funcional a mantém na chave.
            ambientes.append(env)
    valores['ambientes'] = sorted({hash_json(a):a for a in ambientes}.values(), key=hash_json)
    valores['timeouts_s'] = {'T0': 120, 'T2': 60, 'T3': 300, 'T4': 300}
    return valores
