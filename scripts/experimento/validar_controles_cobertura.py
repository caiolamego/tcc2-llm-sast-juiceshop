#!/usr/bin/env python3
"""Comprova controles de regressão funcionais, sem SAST ou chamadas LLM.

Usa âncoras únicas em checkout limpo e restaura apenas os bytes que escreveu.
Resultados são publicados em diretório novo, sem modificar baselines anteriores.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402

from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.comum.identidade import digest
from pipeline.etapas.e02_catalogo.catalogo import carregar as carregar_catalogo
from pipeline.etapas.e06_aplicacao.worktrees import reservar_execucao
from pipeline.etapas.e07_validacao import cobertura
from pipeline.etapas.e07_validacao.execucao_cobertura import executar_grupo


def conferir_checkout(wt, commit):
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=wt, text=True).strip() != commit:
        raise ValueError('Checkout em commit diferente do catálogo')
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=wt, text=True).strip():
        raise ValueError('Checkout alterado; restauração automática de arquivos desconhecidos recusada')


def executar(args):
    reservar_execucao(RAIZ_REPO)
    wt = args.checkout.resolve()
    catalogo = carregar_catalogo(args.catalogo)
    conferir_checkout(wt, catalogo.commit)
    data = cobertura.carregar(args.revisao, args.mapa_testes, wt, catalogo)
    specification = json.loads(args.controles.read_text())
    if specification.get('schema_versao') != '1.0' or not specification.get('controles'):
        raise ValueError('Especificação de controles inválida')
    controls = specification['controles']
    ids = set()
    for control in controls:
        cid = control['id']
        if not isinstance(cid, str) or not cid or Path(cid).name != cid or cid in {'.', '..'} or cid in ids:
            raise ValueError('ID de controle inválido/duplicado')
        ids.add(cid)
        if control['grupo'] not in data['grupos'] or not control.get('teste_esperado'):
            raise ValueError('Controle sem grupo/teste esperado')
        source = cobertura.interno(wt, control['arquivo'])
        if not control.get('antes') or source.read_text().count(control['antes']) != 1:
            raise ValueError('Âncora de controle não é única: ' + cid)
        if not isinstance(control.get('depois'), str) or control['antes'] == control['depois']:
            raise ValueError('Mutação vazia: ' + cid)
    output = args.saida.resolve()
    if output.exists() or not output.is_relative_to(RAIZ_REPO / 'outputs'):
        raise ValueError('Use uma saída nova dentro de outputs/')
    output.mkdir(parents=True, exist_ok=False)
    identity = cobertura.identidade(data, args.revisao, args.mapa_testes)
    report = {
        'schema_versao': '1.0', 'tipo': 'controles_regressao_sem_llm',
        'commit_alvo': catalogo.commit, 'chamadas_llm': 0, 'status': 'parcial',
        'implementacao_sha256': digest(Path(__file__)),
        'cobertura': identity, 'controles_sha256': digest(args.controles), 'controles': []
    }
    lock = threading.Lock()
    healthy = {}
    try:
        for control in controls:
            gid, cid = control['grupo'], control['id']
            if gid not in healthy:
                healthy[gid] = executar_grupo(wt, gid, data['grupos'][gid], output / (gid + '_sadio'), lock_api=lock)
                if not healthy[gid]['comparavel'] or healthy[gid]['falhos']:
                    raise ValueError('Controle sadio não aprovado: ' + gid)
            conferir_checkout(wt, catalogo.commit)
            source = cobertura.interno(wt, control['arquivo'])
            original = source.read_bytes()
            mutant = original.decode().replace(control['antes'], control['depois']).encode()
            source.write_bytes(mutant)
            try:
                broken = executar_grupo(wt, gid, data['grupos'][gid], output / cid, lock_api=lock)
            finally:
                if source.read_bytes() != mutant:
                    raise RuntimeError('Arquivo sofreu alteração desconhecida; restauração recusada: ' + str(source))
                source.write_bytes(original)
            expected_failed = any(t['nome'].split(' > ')[-1] == control['teste_esperado'] and t['estado'] == 'falhou'
                                  for t in broken['testes'])
            detected = not broken['falha_operacional'] and expected_failed
            report['controles'].append({
                **control, 'original_sha256': digest(source),
                'mutante_sha256': hashlib.sha256(mutant).hexdigest(),
                'sadio_aprovado': True, 'falhos_mutante': broken['falhos'],
                'falha_operacional': broken['falha_operacional'], 'detectado': detected,
                'restaurado': source.read_bytes() == original
            })
            conferir_checkout(wt, catalogo.commit)
            print('Controle', cid, 'detectado:', detected, flush=True)
        if cobertura.identidade(data, args.revisao, args.mapa_testes) != identity:
            raise ValueError('Configuração alterada durante os controles')
        if digest(args.controles) != report['controles_sha256']:
            raise ValueError('Especificação alterada durante os controles')
        report['status'] = 'concluido' if all(c['detectado'] for c in report['controles']) else 'reprovado'
    finally:
        report['artefatos_sha256'] = {p.relative_to(output).as_posix(): digest(p)
                                     for p in sorted(output.rglob('*')) if p.is_file()}
        (output / 'controles.json').write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    if report['status'] != 'concluido':
        raise ValueError('Há controles não detectados; consulte controles.json')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('catalogo', 'checkout', 'revisao', 'mapa-testes', 'controles', 'saida'):
        parser.add_argument('--' + name, type=Path, required=True)
    try:
        executar(parser.parse_args(argv))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
