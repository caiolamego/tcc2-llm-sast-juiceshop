"""Controle positivo: a suíte deve aceitar uma troca válida do segredo de teste.

Executar na imagem Docker, após os controles negativos e antes do baseline.
Fonte e resultados ficam juntos como evidência; não é uma correção de segurança.
"""
import hashlib
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from scripts.experimento.validar_controles_cobertura import conferir_checkout
from pipeline.etapas.e06_aplicacao.worktrees import reservar_execucao
from pipeline.etapas.e02_catalogo.catalogo import carregar
from pipeline.etapas.e07_validacao import cobertura
from pipeline.etapas.e07_validacao.execucao_cobertura import executar_grupo


def main():
    reservar_execucao(ROOT)
    wt = ROOT / 'workspace/wt-1'
    catalogo = carregar(ROOT / 'outputs/catalogos/ampliado_v1/catalogo_issues.json')
    conferir_checkout(wt, catalogo.commit)
    revisao = ROOT / 'config/cobertura_funcional_v5.yaml'
    mapa = ROOT / 'config/mapa_testes_relacionados_v6.yaml'
    data = cobertura.carregar(revisao, mapa, wt, catalogo)
    source = wt / 'data/static/users.yml'
    original = source.read_bytes()
    import yaml
    seed = next(user for user in yaml.safe_load(original) if user['key'] == 'timo')
    before = '  totpSecret: ' + seed['totpSecret']
    # Public RFC fixture, deliberately distinct from the original seed. Never deploy it.
    after = '  totpSecret: GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
    if before == after or original.decode().count(before) != 1:
        raise ValueError('Âncora ausente/ambígua ou rotação sem alteração')
    changed = original.decode().replace(before, after).encode()
    output = Path(__file__).resolve().parent.parent / 'rotacao_positiva'
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema_versao': '1.0', 'tipo': 'controle_positivo_rotacao_seed_totp',
              'status': 'parcial', 'commit_alvo': catalogo.commit, 'chamadas_llm': 0,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'original_sha256': hashlib.sha256(original).hexdigest(),
              'rotacionado_sha256': hashlib.sha256(changed).hexdigest(),
              'cobertura': cobertura.identidade(data, revisao, mapa)}
    try:
        healthy = executar_grupo(wt, 'seed_totp', data['grupos']['seed_totp'], output / 'original', lock_api=threading.Lock())
        if not healthy['comparavel'] or healthy['falhos']:
            raise ValueError('Grupo original não aprovado')
        conferir_checkout(wt, catalogo.commit)
        source.write_bytes(changed)
        try:
            rotated = executar_grupo(wt, 'seed_totp', data['grupos']['seed_totp'], output / 'rotacionado', lock_api=threading.Lock())
        finally:
            if source.read_bytes() != changed:
                raise RuntimeError('Alteração desconhecida; restauração recusada')
            source.write_bytes(original)
        conferir_checkout(wt, catalogo.commit)
        report.update(original_aprovado=True, rotacionado_aprovado=bool(rotated['comparavel'] and not rotated['falhos']),
                      restaurado=source.read_bytes() == original, testes_rotacionados=len(rotated['testes']))
        if not report['rotacionado_aprovado']:
            raise ValueError('A avaliação não aceitou a rotação válida')
        report['status'] = 'concluido'
    finally:
        report['artefatos_sha256'] = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(output.rglob('*')) if p.is_file()}
        (output / 'rotacao.json').write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print('Rotação positiva: nove testes aprovados; seed original restaurado.', flush=True)


if __name__ == '__main__':
    main()
