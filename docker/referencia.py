#!/usr/bin/env python3
"""Vincula imagem Docker imutável, baseline validado e entradas versionadas."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT/'docker/referencia.json'
BASELINE = 'outputs/baselines/docker/oficial_v1/BASELINE/baseline_testes.json'
TAG = 'tcc2-llm-sast-juiceshop:1.0'
INPUTS = ('Dockerfile','requirements.lock.txt','docker/juice-shop/package-lock.json',
          'docker/juice-shop/frontend/package-lock.json','config/cobertura_funcional_v1.yaml',
          'config/mapa_testes_relacionados_v2.yaml','config/conjunto_d_cobertura_v1.json',
          'src/pipeline/validation/coverage.py','src/pipeline/validation/coverage_runner.py',
          'src/pipeline/validation/runner.py','src/pipeline/validation/conjunto_d.py',
          'src/pipeline/validation/preparacao_api.py','src/pipeline/validation/coverage_api_setup.mjs',
          'src/pipeline/validation/identity.py','tests/functional/juice_shop/review_likes.test.ts',
          'tests/functional/juice_shop/helpers.spec.ts','tests/functional/juice_shop/insecurity.unit.test.ts')


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


def local(path, root=ROOT):
    p=Path(path)
    if p.is_absolute() or '..' in p.parts:raise ValueError('Caminho relativo inválido')
    dest=(root/p).resolve()
    if not dest.is_relative_to(root.resolve()):raise ValueError('Caminho externo à referência')
    return dest


def read(path):
    def unique(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('Chave JSON duplicada')
            out[k]=v
        return out
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=unique)


def image_id(image):
    data=json.loads(subprocess.check_output(['docker','image','inspect',image],text=True))[0]
    if data['Architecture']!='amd64' or data['Os']!='linux':raise ValueError('Imagem deve ser linux/amd64')
    return data['Id']


def validate(ref, root=ROOT):
    fields={'schema_versao','imagem_id','plataforma','baseline','baseline_sha256',
            'artefatos_sha256','entradas_sha256','comparacao','comparacao_sha256'}
    if not isinstance(ref,dict) or set(ref)!=fields:
        raise ValueError('Schema de referência Docker inválido')
    if ref.get('schema_versao')!='1.0' or not re.fullmatch(r'sha256:[0-9a-f]{64}',ref.get('imagem_id','')):
        raise ValueError('Referência Docker inválida')
    if ref.get('plataforma')!='linux/amd64':raise ValueError('Plataforma inválida')
    baseline=local(ref['baseline'],root)
    if digest(baseline)!=ref['baseline_sha256']:raise ValueError('Baseline oficial alterado')
    data=read(baseline)
    if data.get('status')!='concluido' or data.get('schema_versao')!='2.0' or data.get('chamadas_llm')!=0:
        raise ValueError('Baseline incompleto/incompatível')
    if data.get('artefatos_sha256')!=ref['artefatos_sha256']:raise ValueError('Inventário de evidências divergente')
    for name,h in ref['artefatos_sha256'].items():
        if digest(local(name,baseline.parent))!=h:raise ValueError('Evidência alterada: '+name)
    if set(ref['entradas_sha256'])!=set(INPUTS):raise ValueError('Inventário de entradas divergente')
    for name,h in ref['entradas_sha256'].items():
        if digest(local(name,root))!=h:raise ValueError('Entrada mudou; exige nova referência: '+name)
    report=read(local(ref['comparacao'],root))
    if digest(local(ref['comparacao'],root))!=ref['comparacao_sha256'] or not equivalent(report):
        raise ValueError('Comparação funcional inválida')
    if report['docker']['sha256']!=ref['baseline_sha256']:
        raise ValueError('Comparação não pertence ao baseline oficial')
    return data


def equivalent(report):
    return (report.get('commit_alvo_igual') is True and report.get('cobertura_igual') is True
            and report.get('grupos_total',0)>0
            and report.get('grupos_equivalentes')==report.get('grupos_total')
            and all(v==[True,True] for v in report.get('compilacoes',{}).values()))


def publish(path, ref):
    """Publicação sem sobrescrita, inclusive sob concorrência."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    lock=path.with_name(path.name+'.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    temp=None
    try:
        os.close(fd)
        if path.exists() or path.is_symlink():raise ValueError('Referência existente; não será sobrescrita')
        with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,encoding='utf-8') as f:
            temp=Path(f.name);json.dump(ref,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
            f.flush();os.fsync(f.fileno())
        temp.chmod(0o644)
        # hard link falha se outro processo já publicou o destino.
        os.link(temp,path)
    finally:
        if temp is not None:temp.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


def run_container(image,command):
    return subprocess.run(['docker','compose','run','--rm','-T','tcc',*command],cwd=ROOT,
                          env={**os.environ,'TCC_DOCKER_IMAGE':image},check=True)


def generate(reference):
    reference=Path(reference).resolve()
    if reference.exists():
        ref=read(reference);validate(ref)
        if image_id(ref['imagem_id'])!=ref['imagem_id']:raise ValueError('Imagem oficial indisponível')
        print('Referência existente íntegra; nenhum teste foi repetido.');return
    image=image_id(TAG)
    baseline=ROOT/BASELINE
    # Somente o mantenedor gera uma versão nova; não é ação automática de execução.
    if baseline.parent.exists():raise ValueError('Candidato já existe; investigue-o, não será sobrescrito')
    run_container(image,['python','scripts/experiment/validate_functional_coverage.py',
        '--catalogo','outputs/catalogos/ampliado_v1/catalogo_issues.json','--checkout','workspace/wt-1',
        '--mapa-testes','config/mapa_testes_relacionados_v2.yaml','--revisao','config/cobertura_funcional_v1.yaml',
        '--saida',str(baseline.parent.relative_to(ROOT))])
    freeze(reference,image,baseline)


def freeze(reference,image,baseline):
    reference=Path(reference).resolve()
    if not reference.is_relative_to(ROOT):raise ValueError('Referência deve ficar dentro do projeto')
    image=image_id(image);baseline=Path(baseline).resolve()
    if not baseline.is_relative_to(ROOT):raise ValueError('Baseline fora do projeto')
    report=baseline.parent.parent/'comparacao_DOCKER_V2.json'
    if not report.exists():
        run_container(image,['python','scripts/audit/compare_functional_baselines.py',
            '--referencia','outputs/revalidacoes/DOCKER_V2/BASELINE/baseline_testes.json',
            '--novo',baseline.relative_to(ROOT).as_posix(),'--saida',report.relative_to(ROOT).as_posix()])
    if not equivalent(read(report)):raise ValueError('Resultados diferentes do baseline anterior; referência não publicada')
    run_container(image,['python','docker/referencia.py','verificar-alvo','--baseline',baseline.relative_to(ROOT).as_posix()])
    data=read(baseline)
    ref={'schema_versao':'1.0','imagem_id':image,'plataforma':'linux/amd64',
         'baseline':baseline.relative_to(ROOT).as_posix(),'baseline_sha256':digest(baseline),
         'artefatos_sha256':data['artefatos_sha256'],
         'entradas_sha256':{p:digest(ROOT/p) for p in INPUTS},
         'comparacao':report.relative_to(ROOT).as_posix(),'comparacao_sha256':digest(report)}
    validate(ref)
    publish(reference,ref)
    print('Imagem e baseline congelados em',reference.relative_to(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acao',choices=('imagem','conferir','gerar','congelar','verificar-alvo','exportar','importar'))
    parser.add_argument('--referencia',type=Path,default=REFERENCE)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--imagem',default=TAG)
    parser.add_argument('--arquivo',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.acao=='imagem':
            image=read(args.referencia)['imagem_id'] if args.referencia.exists() else TAG
            if image!=TAG and not re.fullmatch(r'sha256:[0-9a-f]{64}',image):
                raise ValueError('ID imutável de imagem inválido')
            print(image);return 0
        if args.acao=='gerar':generate(args.referencia);return 0
        if args.acao=='congelar':
            if args.baseline is None:parser.error('--baseline obrigatório')
            freeze(args.referencia,args.imagem,args.baseline);return 0
        if args.acao=='verificar-alvo':
            if args.baseline is None:parser.error('--baseline obrigatório')
            sys.path.insert(0,str(ROOT/'src'))
            from pipeline.validation import coverage as c
            from pipeline.catalogo import carregar
            from pipeline.target.workspace import reservar_execucao
            reservar_execucao(ROOT)
            cat=carregar(ROOT/'outputs/catalogos/ampliado_v1/catalogo_issues.json')
            rev=ROOT/'config/cobertura_funcional_v1.yaml';mapa=ROOT/'config/mapa_testes_relacionados_v2.yaml'
            data=c.carregar(rev,mapa,ROOT/'workspace/wt-1',cat)
            # Verifica ambiente e todos os grupos, inclusive os de casos não preparados.
            selection={'dominios':sorted({g['dominio'] for g in data['grupos'].values()}),'grupos':sorted(data['grupos'])}
            c.validar_baseline(args.baseline,data,rev,mapa,ROOT/'workspace/wt-1',selection)
            print('Baseline confere com o ambiente e os grupos da referência');return 0
        if not args.referencia.exists():
            raise ValueError('Referência oficial ausente. Receba docker/referencia.json e suas evidências; '
                             'o mantenedor pode criá-la com make docker-baseline.')
        ref=read(args.referencia);validate(ref)
        if args.acao=='importar':
            if args.arquivo is None:parser.error('--arquivo obrigatório')
            subprocess.run(['docker','image','load','--input',str(args.arquivo)],check=True)
        if image_id(ref['imagem_id'])!=ref['imagem_id']:raise ValueError('Imagem oficial ausente; importe-a com docker-import')
        if args.acao=='exportar':
            if args.arquivo is None:parser.error('--arquivo obrigatório')
            # Reserva o destino e remove somente o arquivo criado aqui, em caso de falha.
            with args.arquivo.open('xb') as f:
                try:subprocess.run(['docker','image','save',ref['imagem_id']],stdout=f,check=True)
                except BaseException:args.arquivo.unlink(missing_ok=True);raise
            print('SHA256 da imagem exportada:',digest(args.arquivo))
        print('Referência Docker conferida:',ref['imagem_id'])
        return 0
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as exc:
        print('ERRO:',exc,file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
