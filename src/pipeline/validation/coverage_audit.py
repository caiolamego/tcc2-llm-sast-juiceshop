"""Auditoria somente por leitura e publicação determinística da cobertura."""
from collections import Counter
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

from pipeline.caminhos import RAIZ_REPO
from pipeline.catalogo import carregar as carregar_catalogo
from pipeline.validation import coverage as c
from pipeline.validation.identity import digest
from pipeline.metrics.exporter import json_bytes,csv_bytes,_promover_exclusivo


def publicar(destino, artifacts, entradas):
    destino=Path(destino).absolute();resolved=destino.resolve()
    if destino.exists() or destino.is_symlink():raise ValueError('Destino existente; use saída nova')
    if resolved in (RAIZ_REPO,RAIZ_REPO/'outputs') or any(Path(p).resolve().is_relative_to(resolved) for p in entradas):
        raise ValueError('Saída sobreposta às entradas')
    if any(resolved.is_relative_to(RAIZ_REPO/p) for p in ('src','workspace','config','rules','knowledge_base','tests')):
        raise ValueError('Saída em área protegida')
    destino.parent.mkdir(parents=True,exist_ok=True);lock=destino.with_name(destino.name+'.lock');tmp=None
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError as exc:raise ValueError('Lock existente; investigue o processo proprietário antes de removê-lo') from exc
    try:
        with os.fdopen(fd,'w') as f:f.write(str(os.getpid())+'\n')
        tmp=Path(tempfile.mkdtemp(prefix='.'+destino.name+'-',dir=destino.parent))
        for name,raw in sorted(artifacts.items()):
            if Path(name).name!=name:raise ValueError('Nome de artefato inválido')
            (tmp/name).write_bytes(raw)
        for path,h in entradas.items():
            if digest(path)!=h:raise ValueError('Entrada alterada durante publicação')
        _promover_exclusivo(tmp,destino);tmp=None
    finally:
        if tmp:shutil.rmtree(tmp)
        lock.unlink(missing_ok=True)


def auditar(catalogo,checkout,mapa,revisao,baseline=None):
    checkout=Path(checkout).resolve();cat=carregar_catalogo(catalogo)
    if not cat.ampliado:raise ValueError('Cobertura requer catálogo ampliado')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()!=cat.commit:
        raise ValueError('Commit do checkout divergente')
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=checkout,text=True).strip():
        raise ValueError('Checkout alterado; auditor não restaura arquivos')
    data=c.carregar(revisao,mapa,checkout,cat)
    inputs={Path(p).resolve():digest(p) for p in (catalogo,mapa,revisao)}
    for source in (Path(__file__),Path(c.__file__),RAIZ_REPO/'scripts/audit/audit_functional_coverage.py'):
        if source.is_file():inputs[source.resolve()]=digest(source)
    for name in ('catalogo_meta.json','exclusoes.json'):
        p=Path(catalogo).parent/name;inputs[p.resolve()]=digest(p)
    for name,h in cat.meta['arquivos_fonte'].items():
        path=c.interno(checkout,name)
        if digest(path)!=h:raise ValueError('Fonte do catálogo alterada')
        inputs[path]=h
    dp=c.interno(RAIZ_REPO,data['conjunto_d']['arquivo']);inputs[dp]=digest(dp)
    for group in data['grupos'].values():
        for test in group['testes']:
            p=c.interno(checkout if test['origem']=='alvo' else RAIZ_REPO,test['arquivo'])
            if digest(p)!=test['sha256']:raise ValueError('Avaliador divergente: '+test['arquivo'])
            inputs[p]=digest(p)
    base=None
    if baseline:
        inputs[Path(baseline).resolve()]=digest(baseline)
        base=c.validar_baseline(baseline,data,revisao,mapa,checkout,{'grupos':[],'dominios':[]},False)
        for name,h in base.get('artefatos_sha256',{}).items():
            p=c.interno(Path(baseline).resolve().parent,name)
            if digest(p)!=h:raise ValueError('Evidência baseline adulterada')
            inputs[p]=h
    rows=[]
    for case in sorted(data['casos'],key=lambda x:x['caso_id']):
        selection=c.selecionar(data,[case['arquivo']],checkout)
        groups=[base.get('grupos',{}).get(g) for g in selection['grupos']] if base else []
        comparable=bool(groups) and all(g and g.get('comparavel') for g in groups)
        comps=sorted({d for g in selection['grupos'] for d in data['grupos'][g]['compilacoes']})
        compiled=bool(base) and all(base.get('compilacoes',{}).get(d,{}).get('passou') for d in comps)
        ready=case['revisao']=='adequada' and selection['suficiente'] and comparable and compiled
        state='comparavel' if comparable and compiled else 'nao_executada' if not groups or any(g is None for g in groups) else 'inconclusiva'
        if base and any(g and g.get('falha_operacional') in ('comando_nao_encontrado','falha_operacional_sem_testes') for g in groups):
            state='bloqueada_ambiente'
        rows.append({**case,'grupos_necessarios_arquivo':selection['grupos'],'dominios':selection['dominios'],
                     'execucao_baseline':state,'elegivel_f_positivo':bool(ready),'motivos_selecao':selection['motivos']})
    files=[]
    for name in sorted({r['arquivo'] for r in rows}):
        sub=[r for r in rows if r['arquivo']==name]
        files.append({'arquivo':name,'casos':len(sub),'casos_ids':[r['caso_id'] for r in sub],
                      'revisoes':dict(Counter(r['revisao'] for r in sub)),
                      'preparados':sum(r['elegivel_f_positivo'] for r in sub)})
    gaps=[{'caso_id':r['caso_id'],'arquivo':r['arquivo'],'lacunas':r['lacunas'],
           'testes_adicionais':r['testes_adicionais'],'baseline':r['execucao_baseline'],
           'motivos':r['motivos_selecao']} for r in rows if not r['elegivel_f_positivo']]
    summary={'casos':len(rows),'arquivos':len(files),'revisoes':dict(Counter(r['revisao'] for r in rows)),
             'baseline':dict(Counter(r['execucao_baseline'] for r in rows)),
             'preparados':sum(r['elegivel_f_positivo'] for r in rows),
             'bloqueados':sum(not r['elegivel_f_positivo'] for r in rows),
             'campanha_78_preparada':all(r['elegivel_f_positivo'] for r in rows),
             'dominios':{d:sum(d in r['dominios'] for r in rows) for d in sorted(c.DOMINIOS)},
             'criterio':'adequacao + uniao por arquivo + baseline comparavel + compilacao aplicavel'}
    artifacts={}
    for name,records in [('cobertura_por_caso',rows),('cobertura_por_arquivo',files)]:
        artifacts[name+'.json']=json_bytes(records)
        columns=sorted({k for r in records for k in r})
        artifacts[name+'.csv']=csv_bytes(columns,records)
    artifacts['lacunas.json']=json_bytes(gaps);artifacts['resumo.json']=json_bytes(summary)
    plan=['# Pendências de cobertura funcional','', 'Revisão insuficiente não exclui casos do catálogo.','']
    for gap in gaps:
        plan.append('- '+gap['caso_id']+' (`'+gap['arquivo']+'`): '+'; '.join(gap['testes_adicionais'] or gap['lacunas'] or gap['motivos'] or ['Executar a seleção e registrar baseline comparável.']))
    artifacts['plano_testes_adicionais.md']=('\n'.join(plan)+'\n').encode()
    def label(p):
        if p.is_relative_to(checkout):return 'alvo/'+p.relative_to(checkout).as_posix()
        if p.is_relative_to(RAIZ_REPO):return 'projeto/'+p.relative_to(RAIZ_REPO).as_posix()
        return 'externo/'+p.name
    artifacts['manifesto.json']=json_bytes({'schema_versao':'1.0','commit_alvo':cat.commit,
        'catalogo_sha256':digest(catalogo),'revisao_sha256':digest(revisao),'chamadas_llm':0,'testes_executados_pelo_auditor':0,
        'fontes_sha256':{label(p):h for p,h in sorted(inputs.items())},
        'artefatos_sha256':{n:__import__('hashlib').sha256(b).hexdigest() for n,b in sorted(artifacts.items())}})
    return artifacts,inputs,summary
