"""Opções públicas e identidade científica da validação."""
from pathlib import Path
from pipeline.comum.caminhos import RAIZ_REPO

DEFAULTS = {'politica_validacao': 'historica_v1', 'mapa_testes': None,
            'cache_validacao': 'desligado', 'repeticao_api': 'ampla'}
CHOICES = {'politica_validacao': ('historica_v1', 'otimizada_v1', 'relacionada_v1', 'relacionada_v2'),
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
    parser.add_argument('--cobertura-funcional',type=Path)


def opcoes(args):
    valores = {k: getattr(args, k, v) for k, v in DEFAULTS.items()}
    for k, choices in CHOICES.items():
        if valores[k] not in choices:
            raise ValueError(f'{k} inválido')
    mapa = valores['mapa_testes']
    if valores['politica_validacao'] in ('otimizada_v1', 'relacionada_v1', 'relacionada_v2') and not mapa:
        raise ValueError('Política de testes relacionados requer --mapa-testes')
    if mapa:
        valores['mapa_testes'] = Path(mapa).resolve()
    cobertura=getattr(args,'cobertura_funcional',None)
    if valores['politica_validacao']=='relacionada_v2':
        if not cobertura:raise ValueError('relacionada_v2 requer --cobertura-funcional')
        if valores['repeticao_api']!='ampla':raise ValueError('relacionada_v2 requer repetição integral do grupo')
        valores['cobertura_funcional']=Path(cobertura).resolve()
    elif cobertura:raise ValueError('--cobertura-funcional requer relacionada_v2')
    return valores


def alterada(args):
    return any(v != DEFAULTS.get(k) for k, v in opcoes(args).items())


def identidade(args, worktrees):
    from pipeline.comum.identidade import digest, hash_json, ambiente
    valores = opcoes(args)
    mapa = valores.pop('mapa_testes')
    cobertura=valores.pop('cobertura_funcional',None)
    valores['mapa_testes_sha256'] = digest(mapa) if mapa else None
    from pipeline.comum.componentes import componentes
    valores['implementacao'] = componentes()
    if cobertura:
        from pipeline.etapas.e07_validacao.cobertura import ler_yaml,identidade as identidade_cobertura
        valores['cobertura']=identidade_cobertura(ler_yaml(cobertura),cobertura,mapa)
        valores['baseline_sha256']=digest(args.baseline_testes)
    ambientes = []
    for wt in (() if getattr(args,'somente_preflight',False) else worktrees):
        if (wt / 'node_modules').is_dir():
            if cobertura:
                from pipeline.etapas.e07_validacao.cobertura import ambiente as ambiente_cobertura
                env=ambiente_cobertura(wt,(wt/'frontend/node_modules').is_dir())
            else:env = ambiente(wt)
            env.pop('porta_api')  # Porta do slot é operacional; a evidência funcional a mantém na chave.
            ambientes.append(env)
    valores['ambientes'] = sorted({hash_json(a):a for a in ambientes}.values(), key=hash_json)
    valores['timeouts_s'] = {'T0': 120, 'T2': 60, 'T3': 300, 'T4': 300}
    if cobertura:valores['timeouts_s'].update(T0_FRONTEND=300,T_FRONTEND=300)
    return valores
