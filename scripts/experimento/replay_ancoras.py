#!/usr/bin/env python3
"""Reaplica respostas com âncora ausente em cópias temporárias; não executa LLM/SAST/testes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e06_aplicacao import aplicador
from pipeline.etapas.e01_analise_sast.estrutura import identidade as identidade_parser


def sha(data):return hashlib.sha256(data).hexdigest()
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')


def replay(execution, checkout, output):
    execution,checkout,output=execution.resolve(),checkout.resolve(),output.resolve()
    if not execution.is_relative_to(RAIZ_REPO/'outputs') or not output.is_relative_to(RAIZ_REPO/'outputs'):
        raise ValueError('Execução e saída devem ficar em outputs/')
    if output.exists() or output.is_relative_to(execution) or execution.is_relative_to(output):raise ValueError('Saída existente/sobreposta')
    records_file=execution/'resultados_consolidados/execucoes.jsonl'
    source_hash=sha(records_file.read_bytes());records=[json.loads(line) for line in records_file.read_text().splitlines() if line.strip()]
    selected=[r for r in records if r.get('status_aplicacao')=='ancora_nao_encontrada']
    if not selected:raise ValueError('Nenhuma tentativa com âncora ausente')
    if len({r['tentativa_id'] for r in selected})!=len(selected):raise ValueError('Tentativa duplicada')
    commits={r['commit_alvo'] for r in selected}
    if len(commits)!=1:raise ValueError('Commits divergentes')
    commit=commits.pop()
    if subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()!=commit:
        raise ValueError('Checkout parser em outro commit')
    parser=identidade_parser(checkout)
    tracked={records_file:source_hash};results=[]
    output.parent.mkdir(parents=True,exist_ok=True);lock=output.with_name(output.name+'.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    staging=Path(tempfile.mkdtemp(prefix='.replay_ancoras_',dir=output.parent))
    try:
        for record in selected:
            tid=record['tentativa_id']
            if Path(tid).name!=tid:raise ValueError('ID de tentativa inválido')
            response=execution/'respostas_llm'/f'{tid}.json'
            if not response.resolve().is_relative_to(execution):raise ValueError('Resposta externa')
            raw=response.read_bytes();tracked[response]=sha(raw)
            correction=aplicador.interpretar(json.loads(raw)['texto'])
            if isinstance(correction,aplicador.ResultadoAplicacao):raise ValueError('Resposta sem correção válida')
            sources={}
            with tempfile.TemporaryDirectory(prefix='tcc_replay_ancora_') as temp:
                root=Path(temp)
                for edit in correction.edicoes:
                    path=Path(edit.arquivo)
                    if path.is_absolute() or '..' in path.parts:raise ValueError('Caminho inválido')
                    source=subprocess.check_output(['git','-C',str(checkout),'show',f'{commit}:{path.as_posix()}'])
                    sources[path.as_posix()]=source
                    target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source)
                result=aplicador.aplicar(root,correction,checkout_parser=checkout)
                row={'tentativa_original':tid,'caso_id':record['caso_id'],'estrategia':record['estrategia_prompt'],
                     'status_original':record['status_aplicacao'],'status_replay':result.status,'detalhe':result.detalhe,
                     'resposta_sha256':sha(raw),'correspondencias':result.correspondencias,
                     'fontes_sha256':{f:sha(b) for f,b in sources.items()}}
                if result.status=='aplicado':
                    diff=[]
                    for name in result.arquivos:
                        data=(root/name).read_bytes();dest=staging/'codigos'/tid/name
                        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
                        diff.extend(difflib.unified_diff(sources[name].decode().splitlines(keepends=True),data.decode().splitlines(keepends=True),fromfile='a/'+name,tofile='b/'+name))
                    patch=staging/'patches'/f'{tid}.diff';patch.parent.mkdir(exist_ok=True);patch.write_text(''.join(diff),encoding='utf-8')
                results.append(row);print(tid,result.status,flush=True)
        if any(sha(path.read_bytes())!=h for path,h in tracked.items()):raise ValueError('Entrada alterada durante replay')
        if identidade_parser(checkout)!=parser:raise ValueError('Parser alterado durante replay')
        report={'schema_versao':'1.0','tipo':'replay_aplicacao_apenas','execucao_original':execution.relative_to(RAIZ_REPO).as_posix(),
                'commit_alvo':commit,'aplicador_versao':aplicador.VERSAO,'parser':parser,
                'implementacao_sha256':{p.name:sha(p.read_bytes()) for p in (Path(aplicador.__file__),Path(aplicador.__file__).with_name('indentacao.py'))},
                'entradas_sha256':{p.relative_to(RAIZ_REPO).as_posix():h for p,h in tracked.items()},
                'tentativas':results,'total':len(results),'aplicadas':sum(r['status_replay']=='aplicado' for r in results),
                'chamadas_llm':0,'sast_executado':False,'testes_funcionais_executados':False,'alvo_modificado':False}
        dump(staging/'replay.json',report)
        dump(staging/'manifesto.json',{'schema_versao':'1.0','artefatos_sha256':{p.relative_to(staging).as_posix():sha(p.read_bytes()) for p in sorted(staging.rglob('*')) if p.is_file()}})
        if output.exists():raise ValueError('Saída apareceu durante o replay')
        staging.rename(output)
        return report
    finally:
        if staging.exists():shutil.rmtree(staging)
        lock.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('execucao','checkout-parser','saida'):parser.add_argument('--'+flag,type=Path,required=True)
    args=parser.parse_args()
    try:
        report=replay(args.execucao,args.checkout_parser,args.saida)
        print(f"{report['aplicadas']}/{report['total']} respostas aplicáveis; sem LLM, SAST ou testes funcionais")
        return 0 if report['aplicadas']==report['total'] else 1
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc:
        print('ERRO:',exc,file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
