"""Execução funcional por grupos, Angular e evidências completas de seleção."""
from contextlib import contextmanager, nullcontext
from pathlib import Path
import html
import json
import os
import tempfile
import time
import xml.etree.ElementTree as ET

from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e07_validacao import cobertura as c
from pipeline.comum.identidade import digest


@contextmanager
def staging(wt, group):
    created=[];parents=[]
    try:
        for test in group['testes']:
            if test['origem']!='avaliacao':continue
            source=c.interno(RAIZ_REPO,test['arquivo']);dest=c.interno(wt,test['destino'])
            if digest(source)!=test['sha256']:raise ValueError('Teste adicional alterado')
            missing=[];parent=dest.parent
            while not parent.exists():missing.append(parent);parent=parent.parent
            dest.parent.mkdir(parents=True,exist_ok=True);parents.extend(reversed(missing))
            with dest.open('xb') as f:f.write(source.read_bytes())
            created.append((dest,test['sha256']))
        yield
    finally:
        for path,h in reversed(created):
            if not path.is_file() or digest(path)!=h:
                raise RuntimeError('Avaliação temporária alterada; limpeza automática recusada: '+str(path))
            path.unlink()
        for path in reversed(parents):
            if path.exists() and not any(path.iterdir()):path.rmdir()


def relatorio(xml, wt, group):
    if not Path(xml).is_file():raise ValueError('Relatório JUnit ausente')
    try:root=ET.parse(xml).getroot()
    except ET.ParseError as exc:raise ValueError('JUnit inválido') from exc
    aliases={t.get('destino',t['arquivo']):t['arquivo'] for t in group['testes']}
    expected=set(aliases);records=[]
    def visit(node,suites):
        for child in node:
            if child.tag=='testsuite':
                visit(child,suites+[html.unescape(child.get('name',''))])
            elif child.tag=='testcase':
                raw=child.get('file') or child.get('classname','')
                if raw.startswith(str(wt.resolve())+'/'):raw=Path(raw).relative_to(wt.resolve()).as_posix()
                if group['dominio']=='frontend' and not raw.startswith('frontend/'):raw='frontend/'+raw
                if raw not in expected:raise ValueError('Teste executado fora da seleção: '+raw)
                if group['dominio']=='frontend':name=html.unescape(child.get('name',''))
                else:name=' > '.join(n for n in suites+[html.unescape(child.get('name',''))] if n and n!=raw)
                file=aliases[raw]
                if not name.strip():raise ValueError('Falha de carregamento do arquivo sem identidade de teste')
                records.append({'id':file+' :: '+name,'arquivo':file,'nome':name,
                                'estado':'ignorado' if child.find('skipped') is not None else
                                         'falhou' if child.find('failure') is not None or child.find('error') is not None else 'passou'})
            else:visit(child,suites)
    visit(root,[])
    if not records or len({r['id'] for r in records})!=len(records):raise ValueError('Relatório vazio ou identidades duplicadas')
    actual={r['arquivo'] for r in records}
    if actual!={t['arquivo'] for t in group['testes']}:raise ValueError('Arquivo selecionado não executado')
    return sorted(records,key=lambda r:r['id'])


def obrigatorios(group, records):
    missing=[];ids=[]
    for requirement in group['obrigatorios']:
        matches=[r for r in records if r['arquivo']==requirement['arquivo'] and
                 r['nome'].split(' > ')[-1]==requirement['nome']]
        if not matches or any(r['estado']!='passou' for r in matches):missing.append(requirement)
        else:ids.extend(r['id'] for r in matches)
    return ids,missing


def compilar(wt, dominio, output):
    from pipeline.etapas.e07_validacao.camadas import _rodar
    with tempfile.TemporaryDirectory(prefix='tcc_angular_build_') as temp:
        return _compilar(wt,dominio,Path(temp))


def _compilar(wt, dominio, output):
    from pipeline.etapas.e07_validacao.camadas import _rodar
    if dominio=='frontend':
        cmd=['node','node_modules/@angular/cli/bin/ng.js','build','--configuration=development','--aot=true',
             '--output-path='+str((output/'build_frontend').resolve()),'--progress=false']
        cwd=wt/'frontend';env={'CI':'true','NG_CLI_ANALYTICS':'false'};timeout=300
    else:cmd=['node','node_modules/typescript/bin/tsc','--noEmit'];cwd=wt;env={};timeout=120
    r,_=_rodar('T0_FRONTEND' if dominio=='frontend' else 'T0',cmd,cwd,timeout,env)
    if r.motivo=='timeout':
        second,_=_rodar(r.tier,cmd,cwd,timeout,env);second.reexecucoes=1;second.timeout_na_primeira_rodada=True
        second.duracao_s+=r.duracao_s;r=second
    return r


def executar_grupo(wt, gid, group, output, baseline=None, lock_api=None):
    from pipeline.etapas.e07_validacao.camadas import _rodar, cmd_testes, SETUP_SERVIDOR, SETUP_API, porta_t4, ResultadoTier
    output.mkdir(parents=True,exist_ok=False)
    selection=[t.get('destino',t['arquivo']) for t in group['testes']]
    frontend=group['dominio']=='frontend';api=group['dominio']=='api'
    xml=output/'primeira.xml';records=[];operational=None
    def round_run(xml):
        if api:
            from pipeline.etapas.e07_validacao.preparacao_api import conferir
            try:conferir(wt)
            except (ValueError,OSError) as exc:
                return ResultadoTier('T2_API',[],False,0,motivo='preparacao_api_invalida',saida=str(exc)),[],'preparacao_api_invalida'
        if frontend:
            cmd=['node','node_modules/@angular/cli/bin/ng.js','test','--watch=false','--progress=false',
                 '--reporters=junit','--output-file='+str(xml.resolve())]
            cmd+=['--include='+f.removeprefix('frontend/') for f in selection]
            cwd=wt/'frontend';env={'CI':'true','NG_CLI_ANALYTICS':'false'};timeout=300
        else:
            cmd=cmd_testes(SETUP_API if api else SETUP_SERVIDOR,selection,xml.resolve());cwd=wt
            # No Node 24 o force-exit pode publicar apenas parte de suítes
            # unitárias aninhadas. Unitários terminam naturalmente; APIs mantêm
            # o isolamento existente por conexões abertas.
            if not api:cmd.remove('--test-force-exit')
            else:
                index=cmd.index('--test')
                cmd[index:index]=['--import',str(Path(__file__).with_name('preparo_api_cobertura.mjs').resolve())]
            env={'TSX_DISABLE_CACHE':'1',**({'PORT':str(porta_t4(wt))} if api else {})};timeout=300 if api else 60
        result,_=_rodar('T_FRONTEND' if frontend else 'T2_API' if api else 'T2',cmd,cwd,timeout,env)
        if result.motivo in ('timeout','comando_nao_encontrado'):return result,[],result.motivo
        if 'unsatisfied precondition' in result.saida.lower():
            return result,[],'precondicao_api_nao_satisfeita'
        try:
            parsed=relatorio(xml,wt,group)
            if result.codigo_saida not in (0,1) or (result.codigo_saida and not any(r['estado']=='falhou' for r in parsed)):
                return result,parsed,'falha_operacional_sem_testes'
            return result,parsed,None
        except ValueError as exc:return result,[],str(exc)
    wait=time.monotonic()
    with (lock_api if api and lock_api else nullcontext()):
        wait=time.monotonic()-wait
        with staging(wt,group):
            result,records,operational=round_run(xml)
            failed={r['id'] for r in records if r['estado']=='falhou'}
            old=set(baseline.get('falhos',[])) if baseline else set()
            new=failed-old;intermittent=set();repetitions=0
            if baseline is not None and (new or operational):
                second,again,op2=round_run(output/'segunda.xml');repetitions=1
                result.duracao_s+=second.duracao_s
                if operational or op2:
                    operational=operational or op2  # Timeout não sustenta aprovação nesta política.
                else:
                    next_new={r['id'] for r in again if r['estado']=='falhou'}-old
                    intermittent=new^next_new;new&=next_new
                    # Ausência ou skip em qualquer rodada impede cobertura positiva.
                    if {r['id'] for r in again if r['estado']!='ignorado'} != {r['id'] for r in records if r['estado']!='ignorado'}:
                        operational='selecao_divergente_na_repeticao'
            required,missing=obrigatorios(group,records)
            if baseline is not None:
                expected=set(baseline['executados'])
                if expected != {r['id'] for r in records if r['estado']!='ignorado'}:
                    operational=operational or 'testes_ausentes_ou_ignorados'
            # Falha do harness não é uma asserção funcional persistente.
            observed_new=sorted(new)
            if operational:new=set()
            measured={'grupo':gid,'dominio':group['dominio'],'testes':records,'falhos':sorted(failed),
                      'falhos_novos':sorted(new),'falhos_novos_observados':observed_new,'intermitentes':sorted(intermittent),'reexecucoes':repetitions,
                      'descobertos':sorted(r['id'] for r in records),
                      'esperados':sorted(baseline['executados']) if baseline else sorted(r['id'] for r in records if r['estado']!='ignorado'),
                      'ignorados':sorted(r['id'] for r in records if r['estado']=='ignorado'),
                      'executados':sorted(r['id'] for r in records if r['estado']!='ignorado'),
                      'obrigatorios_aprovados':required,'obrigatorios_ausentes_baseline':missing if baseline is None else [],
                      'falha_operacional':operational,'comparavel':not operational and not missing,
                      'duracao_s':result.duracao_s,'espera_api_s':wait,'resultado':result.to_dict() if hasattr(result,'to_dict') else vars(result)}
            measured['relatorios_junit']={p.name:p.read_text(encoding='utf-8') for p in (xml,output/'segunda.xml') if p.is_file()}
    (output/'resultado.json').write_text(json.dumps(measured,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    return measured


def validar(wt, arquivos, cfg, callback=None):
    from pipeline.etapas.e07_validacao.camadas import ResultadoValidacao,ResultadoTier
    from pipeline.etapas.e07_validacao.conjunto_d import classificar
    start=time.monotonic();wt=Path(wt)
    data=c.carregar(cfg.cobertura,cfg.mapa,wt,permitir_avaliadores_alterados=True);selection=c.selecionar(data,arquivos,wt)
    try:
        baseline=c.validar_baseline(cfg.arquivo_linha_de_base,data,cfg.cobertura,cfg.mapa,wt,selection,exigir_grupos=False)
    except FileNotFoundError:
        baseline=c.validar_baseline(cfg.arquivo_linha_de_base,data,cfg.cobertura,cfg.mapa,wt,selection,False,False)
        selection['suficiente']=False;selection['motivos'].append('dependências de domínio ausentes')
    result=ResultadoValidacao(passou=None,tier_falha=None,duracao_s=0,escopo='relacionado_v2',
                              selecao=selection,cobertura_insuficiente=not selection['suficiente'])
    result.cobertura_detalhada={'dominios':selection['dominios'],'grupos_selecionados':selection['grupos'],
                               'compilacoes':[],'grupos':[],'motivos':list(selection['motivos']),
                               'baseline_sha256':digest(cfg.arquivo_linha_de_base)}
    values={d:True for d in ('sem_separacao','marcador','criterio')};unknown=False
    with tempfile.TemporaryDirectory(prefix='tcc_cobertura_') as folder:
        output=Path(folder)
        comp_domains=sorted({d for g in selection['grupos'] for d in data['grupos'][g]['compilacoes']})
        for domain in comp_domains:
            if domain=='frontend' and not (wt/'frontend/node_modules/@angular/cli').is_dir():
                unknown=True;result.cobertura_detalhada['motivos'].append('adaptador Angular indisponível');continue
            r=compilar(wt,domain,output);result.tiers.append(r)
            result.cobertura_detalhada['compilacoes'].append({'dominio':domain,'tier':r.tier,
                'passou':r.passou,'motivo':r.motivo,'duracao_s':r.duracao_s})
            result.etapas.append({'tier':r.tier,'status':'executada','duracao_s':r.duracao_s})
            if not r.passou:
                if r.motivo in ('timeout','comando_nao_encontrado'):unknown=True
                else:values={d:False for d in values}
                break
        if values['criterio'] and not unknown:
            for gid in selection['grupos']:
                if data['grupos'][gid]['dominio']=='api' and not cfg.rodar_t4:
                    unknown=True;result.cobertura_detalhada['motivos'].append(gid+': API desabilitada');continue
                if baseline.get('grupos',{}).get(gid,{}).get('comparavel') is not True:
                    unknown=True;result.cobertura_detalhada['motivos'].append(gid+': baseline insuficiente');continue
                g=executar_grupo(wt,gid,data['grupos'][gid],output/gid,baseline['grupos'][gid],cfg.lock_t4)
                result.cobertura_detalhada['grupos'].append(g)
                raw=g['resultado'];raw={k:v for k,v in raw.items() if k in ResultadoTier.__dataclass_fields__}
                r=ResultadoTier(**raw);r.testes_falhos_novos=g['falhos_novos'];r.testes_falhos=g['falhos']
                r.reexecucoes=g['reexecucoes'];r.espera_api_s=g['espera_api_s'];r.testes_falhos_intermitentes=g['intermitentes']
                result.tiers.append(r);result.etapas.append({'tier':r.tier,'grupo':gid,'status':'executada','duracao_s':r.duracao_s})
                if g['falha_operacional']:
                    unknown=True;result.cobertura_detalhada['motivos'].append(g['falha_operacional'])
                    continue  # Nenhuma definição de F recebe reprovação de um grupo inválido.
                split=classificar(g['falhos_novos'],RAIZ_REPO/data['conjunto_d']['arquivo'])
                for d in values:
                    failures=g['falhos_novos'] if d=='sem_separacao' else split['f_'+d]
                    if failures:values[d]=False
                result.testes_falhos_novos+=g['falhos_novos'];result.testes_falhos_intermitentes+=g['intermitentes']
                result.testes_falhos_d_marcador+=split['d_marcador'];result.testes_falhos_d_criterio+=split['d_criterio']
                result.testes_falhos_f_marcador+=split['f_marcador'];result.testes_falhos_f_criterio+=split['f_criterio']
                if not values['criterio']:break
        # Todos os testes temporários já saíram; o callback SAST não observa staging.
        callback_time=0
        if callback:
            before=time.monotonic();callback();callback_time=time.monotonic()-before
    result.cobertura_insuficiente |= unknown
    result.cobertura_detalhada['suficiente']=not result.cobertura_insuficiente
    for d,value in values.items():
        setattr(result,'F_'+d,None if value and result.cobertura_insuficiente else value)
        setattr(result,'tier_falha_'+d,'cobertura_insuficiente' if value and result.cobertura_insuficiente else
                None if value else result.tiers[-1].tier)
    result.passou=result.F_criterio;result.tier_falha=result.tier_falha_criterio
    result.duracao_s=time.monotonic()-start-callback_time
    return result
