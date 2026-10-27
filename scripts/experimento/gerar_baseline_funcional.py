#!/usr/bin/env python3
"""Gera baseline por grupos ou executa controles isolados; nunca usa LLM."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
import argparse
import json
import subprocess
import threading
import time

from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e02_catalogo.catalogo import carregar as carregar_catalogo
from pipeline.etapas.e07_validacao import cobertura as c
from pipeline.etapas.e07_validacao.execucao_cobertura import compilar,executar_grupo
from pipeline.comum.identidade import digest
from pipeline.etapas.e06_aplicacao.worktrees import reservar_execucao


def salvar(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')


def controles(wt,output,data):
    import hashlib
    specs=[('insecurity_extra','lib/insecurity.ts',"return hmac.update(email + roles.deluxe).digest('hex')","return ''"),
           ('likes_extra','routes/likeProductReviews.ts','{ $inc: { likesCount: 1 } }','{ $inc: { likesCount: 0 } }'),
           ('instructor','frontend/src/hacking-instructor/helpers/helpers.ts','replacementValue = replacementValue[property]','replacementValue = undefined')]
    rows=[];lock=threading.Lock()
    for gid,file,old,new in specs:
        path=c.interno(wt,file);original=path.read_bytes();text=original.decode()
        if text.count(old)!=1:raise ValueError('Âncora de controle não é única')
        healthy=executar_grupo(wt,gid,data['grupos'][gid],output/(gid+'_sadio'),lock_api=lock)
        mutated=text.replace(old,new).encode();path.write_bytes(mutated)
        try:
            broken=executar_grupo(wt,gid,data['grupos'][gid],output/(gid+'_mutante'),lock_api=lock)
        finally:
            if path.read_bytes()!=mutated:raise RuntimeError('Controle sofreu alteração desconhecida; restauração recusada')
            path.write_bytes(original)
        detected=healthy['comparavel'] and not broken['falha_operacional'] and bool(broken['falhos'])
        rows.append({'grupo':gid,'arquivo':file,'original_sha256':hashlib.sha256(original).hexdigest(),
                     'mutante_sha256':hashlib.sha256(mutated).hexdigest(),'sadio_aprovado':healthy['comparavel'],
                     'falhos_mutante':broken['falhos'],'detectado':detected})
        salvar(output/'controles.json',rows)
        print('Controle',gid,'detectado:',detected,flush=True)
    if not all(r['detectado'] for r in rows):raise ValueError('Controle de regressão não detectado')
    return {'schema_versao':'1.0','tipo':'controles_regressao_sem_llm','controles':rows,'chamadas_llm':0}


def executar(args):
    wt=args.checkout.resolve();output=args.saida.resolve()
    reservar_execucao(RAIZ_REPO)
    cat=carregar_catalogo(args.catalogo)
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=wt,text=True).strip()!=cat.commit:
        raise ValueError('Checkout em commit diferente')
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=wt,text=True).strip():
        raise ValueError('Checkout alterado; nenhum arquivo será restaurado automaticamente')
    data=c.carregar(args.revisao,args.mapa_testes,wt,cat)
    selected=sorted(args.grupos.split(',')) if args.grupos else sorted(data['grupos'])
    if not selected or len(set(selected))!=len(selected) or set(selected)-set(data['grupos']):
        raise ValueError('Grupos inválidos')
    if any(data['grupos'][g]['dominio']=='api' for g in selected):
        from pipeline.etapas.e07_validacao.preparacao_api import conferir
        conferir(wt)
    if output.exists() or output.is_relative_to(RAIZ_REPO/'workspace'):raise ValueError('Destino inválido/existente')
    output.mkdir(parents=True,exist_ok=False)
    if args.controles:
        result=controles(wt,output,data)
        if subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=wt,text=True).strip():
            raise ValueError('Controle deixou checkout modificado')
        salvar(output/'resultado_controles.json',result)
        return result
    identity=c.identidade(data,args.revisao,args.mapa_testes)
    environment=c.ambiente(wt,any(data['grupos'][g]['dominio']=='frontend' for g in selected));environment.pop('porta_api',None)
    baseline={'schema_versao':'2.0','commit_alvo':cat.commit,'cobertura':identity,'ambiente':environment,
              'status':'parcial','grupos':{},'compilacoes':{},'chamadas_llm':0}
    start=time.monotonic();lock=threading.Lock()
    salvar(output/'baseline_testes.json',baseline)
    try:
        for domain in sorted({d for g in selected for d in data['grupos'][g]['compilacoes']}):
            r=compilar(wt,domain,output);baseline['compilacoes'][domain]=vars(r)
            print('Compilação',domain,r.passou,r.motivo,r.duracao_s,flush=True)
        for gid in selected:
            print('Grupo',gid,flush=True)
            result=executar_grupo(wt,gid,data['grupos'][gid],output/gid,lock_api=lock)
            baseline['grupos'][gid]=result
            print('  comparável:',result['comparavel'],'testes:',len(result['testes']),'tempo:',result['duracao_s'],
                  'op:',result['falha_operacional'],'obrigatórios ausentes:',result['obrigatorios_ausentes_baseline'],flush=True)
            salvar(output/'baseline_testes.json',baseline)
        if c.identidade(data,args.revisao,args.mapa_testes)!=identity:raise ValueError('Configuração alterada durante validação')
        if c.ambiente(wt,'frontend' in {data['grupos'][g]['dominio'] for g in selected}) | {'porta_api':None} != environment | {'porta_api':None}:
            raise ValueError('Ambiente alterado durante validação')
        if subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=wt,text=True).strip():
            raise ValueError('Testes deixaram alterações; inspecione sem restaurar arquivos desconhecidos')
        baseline['status']='concluido'
    finally:
        baseline['duracao_s']=time.monotonic()-start
        baseline['artefatos_sha256']={p.relative_to(output).as_posix():digest(p) for p in sorted(output.rglob('*'))
                                     if p.is_file() and p.name!='baseline_testes.json' and 'build_frontend' not in p.parts}
        salvar(output/'baseline_testes.json',baseline)
    return baseline


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('catalogo','checkout','mapa-testes','revisao','saida'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--grupos',help='IDs separados por vírgula; padrão: todos os grupos revisados')
    parser.add_argument('--controles',action='store_true',help='Três mutações conhecidas e temporárias; restaura somente os arquivos que modificou')
    args=parser.parse_args(argv)
    try:
        data=executar(args);print('Concluído:',len(data.get('grupos',data.get('controles',[]))),'grupos/controles');return 0
    except (OSError,ValueError,KeyError,RuntimeError) as exc:print(str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
