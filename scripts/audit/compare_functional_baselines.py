#!/usr/bin/env python3
"""Compara dois baselines funcionais (schema 2.0) por ambiente, compilações e testes de cada grupo.

Uso típico: conferir se um ambiente novo (ex.: Docker) reproduz o comportamento funcional
de um baseline anterior. Não executa testes, Semgrep nem LLM; recusa destino existente.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def achatar(d, prefixo=''):
    for k, v in sorted(d.items()):
        if isinstance(v, dict):
            yield from achatar(v, prefixo + k + '.')
        else:
            yield prefixo + k, v


def comparar(antigo_path, novo_path):
    antigo = json.loads(antigo_path.read_text(encoding='utf-8'))
    novo = json.loads(novo_path.read_text(encoding='utf-8'))
    amb_a, amb_n = dict(achatar(antigo['ambiente'])), dict(achatar(novo['ambiente']))
    ambiente = {k: {'igual': amb_a.get(k) == amb_n.get(k), 'piloto10': amb_a.get(k), 'docker': amb_n.get(k)}
                for k in sorted(set(amb_a) | set(amb_n))}
    grupos = {}
    for gid in sorted(set(antigo['grupos']) | set(novo['grupos'])):
        ga, gn = antigo['grupos'].get(gid), novo['grupos'].get(gid)
        if ga is None or gn is None:
            grupos[gid] = {'presente_piloto10': ga is not None, 'presente_docker': gn is not None}
            continue
        ea = {t['id']: t['estado'] for t in ga['testes']}
        en = {t['id']: t['estado'] for t in gn['testes']}
        g = {
            'comparavel': [ga['comparavel'], gn['comparavel']],
            'testes': [len(ea), len(en)],
            'so_piloto10': sorted(set(ea) - set(en)),
            'so_docker': sorted(set(en) - set(ea)),
            'estado_diferente': {t: [ea[t], en[t]] for t in sorted(set(ea) & set(en)) if ea[t] != en[t]},
            'falhos': [sorted(ga['falhos']), sorted(gn['falhos'])],
            'obrigatorios_aprovados': [sorted(ga['obrigatorios_aprovados']), sorted(gn['obrigatorios_aprovados'])],
        }
        g['equivalente'] = (g['comparavel'][0] == g['comparavel'][1] and not g['so_piloto10'] and not g['so_docker']
                            and not g['estado_diferente'] and g['falhos'][0] == g['falhos'][1]
                            and g['obrigatorios_aprovados'][0] == g['obrigatorios_aprovados'][1])
        grupos[gid] = g
    return {
        'schema_versao': '1.0',
        'tipo': 'comparacao_baselines_funcionais',
        'piloto10': {'arquivo': str(antigo_path), 'sha256': hashlib.sha256(antigo_path.read_bytes()).hexdigest()},
        'docker': {'arquivo': str(novo_path), 'sha256': hashlib.sha256(novo_path.read_bytes()).hexdigest()},
        'commit_alvo_igual': antigo['commit_alvo'] == novo['commit_alvo'],
        'cobertura_igual': antigo['cobertura'] == novo['cobertura'],
        'compilacoes': {k: [antigo['compilacoes'][k]['passou'], novo['compilacoes'][k]['passou']]
                        for k in sorted(set(antigo['compilacoes']) | set(novo['compilacoes']))},
        'ambiente': ambiente,
        'ambiente_diferente': [k for k, v in ambiente.items() if not v['igual']],
        'grupos': grupos,
        'grupos_equivalentes': sum(1 for g in grupos.values() if g.get('equivalente')),
        'grupos_total': len(grupos),
        'duracao_s': [round(antigo['duracao_s'], 1), round(novo['duracao_s'], 1)],
        'chamadas_llm': 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--referencia', type=Path, required=True, help='baseline_testes.json anterior (ex.: piloto de 10 casos)')
    parser.add_argument('--novo', type=Path, required=True, help='baseline_testes.json do ambiente novo (ex.: Docker)')
    parser.add_argument('--saida', type=Path, required=True, help='JSON de saída; não pode existir')
    args = parser.parse_args(argv)
    if args.saida.exists():
        print('Destino existente; nada foi sobrescrito: ' + str(args.saida), file=sys.stderr)
        return 1
    resultado = comparar(args.referencia, args.novo)
    args.saida.write_text(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print('commit igual:', resultado['commit_alvo_igual'], '| cobertura igual:', resultado['cobertura_igual'])
    print('compilações:', resultado['compilacoes'])
    print('ambiente diferente:', resultado['ambiente_diferente'])
    print('grupos equivalentes:', resultado['grupos_equivalentes'], '/', resultado['grupos_total'])
    for gid, g in resultado['grupos'].items():
        if not g.get('equivalente'):
            print('  DIFERENTE', gid, sorted(g.get('estado_diferente', {})) or g)
    print('duração (s) referência x novo:', resultado['duracao_s'])
    return 0 if resultado['grupos_equivalentes'] == resultado['grupos_total'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
