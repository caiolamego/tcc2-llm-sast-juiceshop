"""Cálculos legados e consolidação verificável por população."""
from collections import defaultdict, Counter
import math
from pipeline.metrics.normalizer import DEFS

def v(x):
    return x or 0


def indices(ls: list[dict], d: str) -> dict | None:
    m = len(ls)
    if not m:
        return None
    aceitas = [l for l in ls if l[f"classificacao_{d}"] == "aceita"]
    ampliado = any('assinatura_ocorrencia' in l for l in ls)
    def taxa(campo):
        if ampliado:
            medidos = [l[campo] for l in ls if l[campo] is not None]
            return round(sum(medidos) / len(medidos), 4) if medidos else None
        return round(sum(v(l[campo]) for l in ls) / m, 4)
    return {
        "m": m,
        "TRV": round(sum(v(l["R"]) * v(l[f"F_{d}"]) * v(l["M"]) for l in ls) / m, 4),
        "TRI": taxa("R"),
        "TPF": taxa(f"F_{d}"),
        "TNINI": taxa("M"),
        "TAP": round(sum(l["status_aplicacao"] == "aplicado" for l in ls) / m, 4),
        "aceitas": len(aceitas),
        "TCD": (round(sum(bool(l[f"testes_falhos_d_{d}"]) for l in aceitas) / len(aceitas), 4)
                if aceitas else None),
        "indeterminadas": sum(1 for l in ls if l.get(f"incompleto_{d}")),
        **({'denominadores_medidos': {campo:sum(l[campo] is not None for l in ls) for campo in ('R',f'F_{d}','M')}} if ampliado else {}),
    }


def cadeia(ls: list[dict], d: str, ordem: list[str]) -> list[dict]:
    por_caso = defaultdict(list)
    for l in ls:
        por_caso[l["caso_id"]].append(l)
    saida = []
    for caso in sorted(por_caso):
        for l in sorted(por_caso[caso], key=lambda x: ordem.index(x["estrategia_curta"])):
            saida.append(l)
            if l[f"classificacao_{d}"] == "aceita":
                break
    return saida


def custos(linhas):
    reais = [l for l in linhas if not l.get('dry_run') and l.get('modelo') != 'dry-run']
    nc = [l for l in reais if not l.get('do_cache')]
    return {'chamadas_reais': len(nc), 'do_cache': sum(bool(l.get('do_cache')) for l in reais),
            'simuladas': len(linhas) - len(reais),
            'usd': round(sum(v(l['custo_usd']) for l in nc), 6),
            'tokens_entrada': sum(v(l['tokens_entrada']) for l in nc),
            'tokens_saida': sum(v(l['tokens_saida']) for l in nc)}



def metrica(numerador, denominador, politica, motivo=None):
    return {'valor':numerador/denominador if denominador else None,
            'numerador':numerador,'denominador':denominador,'politica':politica,
            'status':'disponivel' if denominador else 'indisponivel',
            'motivo':motivo if motivo else None if denominador else 'sem_denominador'}


def indisponivel(motivo, politica='nao_aplicavel'):
    return {'valor':None,'numerador':None,'denominador':None,'politica':politica,
            'status':'indisponivel','motivo':motivo}


def metricas(rows, definicao, ampliado, pesos=None):
    m=len(rows)
    aceitas=[r for r in rows if r['status_aplicacao']=='aplicado' and
             (r.get('R'),r.get('F_'+definicao),r.get('M'))==(1,1,1)]
    result={'TRV':metrica(len(aceitas),m,'todas_tentativas'),
            'TAP':metrica(sum(r['status_aplicacao']=='aplicado' for r in rows),m,'todas_tentativas')}
    for name,field in [('TRI','R'),('TPF','F_'+definicao),('TNINI','M')]:
        measured=[r[field] for r in rows if r.get(field) is not None]
        den=len(measured) if ampliado else m
        num=sum(measured)
        result[name]=metrica(num,den,'somente_medidos' if ampliado else 'historica_total')
        result[name+'_minima']=metrica(num,m,'sucessos_comprovados_sobre_total')
    tpf=result['TPF']
    result['TFF']=metrica(tpf['denominador']-tpf['numerador'],tpf['denominador'],tpf['politica'])
    result['TCD']=metrica(sum(bool(r.get('testes_falhos_d_'+definicao)) for r in aceitas),len(aceitas),'indicador_exploratorio_d')
    if pesos is None:
        result['TRV-P']=indisponivel('politica_pesos_ausente')
    elif any(r.get('severidade') not in pesos for r in rows):
        result['TRV-P']=indisponivel('severidade_sem_peso')
    else:
        result['TRV-P']=metrica(math.fsum(pesos[r['severidade']] for r in aceitas),
                               math.fsum(pesos[r['severidade']] for r in rows),'pesos_declarados')
    return result


def custos_atual(rows, sessoes):
    real=[r for r in rows if not r['dry_run']]
    calls=[r for r in real if not r.get('do_cache')]
    cached=[r for r in real if r.get('do_cache')]
    def known(ls, key):
        values=[r.get(key) for r in ls]
        present=[]
        for value in values:
            if value is None:continue
            if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                raise ValueError(f'{key} inválido')
            if key.startswith('tokens') and type(value) is not int:raise ValueError('Tokens devem ser inteiros')
            present.append(value)
        return {'total_conhecido':math.fsum(present),'ausentes':len(values)-len(present),
                'completude':'completa' if len(values)==len(present) else 'parcial'}
    errors=sum(len(s.get('erros',[])) for s in sessoes)
    resultado = {'chamadas_novas_registradas':len(calls),'usos_cache':len(cached),
            'simuladas':sum(r['dry_run'] for r in rows),
            'custo_usd':known(calls,'custo_usd'),
            'tokens_chamadas':{k:known(calls,k) for k in ('tokens_entrada','tokens_saida')},
            'tokens_cache':{k:known(cached,k) for k in ('tokens_entrada','tokens_saida')},
            'tempos_acumulados':{k:known(rows,k) for k in ('duracao_sast_s','duracao_validacao_s')},
            'latencia_llm_chamadas':known(calls,'duracao_llm_s'),
            'latencia_llm_cache_registrada':known(cached,'duracao_llm_s'),
            'duracoes_sessoes':[{'inicio':s.get('inicio'),'fim':s.get('fim'),'duracao_s':s.get('duracao_s'),
                                 'abortada':s.get('abortada'),'interrompida_por_orcamento':s.get('interrompida_por_orcamento')} for s in sessoes],
            'erros_sessoes':errors,'limite':'Chamadas sem registro não têm custo/tokens inferidos; durações acumuladas não são tempo de parede.'}
    if any('cache_validacao' in r for r in rows):
        resultado['validacao_reutilizada'] = {
            comp: {'reusos':sum(bool(r.get('cache_validacao',{}).get(comp,{}).get('hit')) for r in rows),
                   'medicoes_executadas':sum(comp in r.get('cache_validacao',{}) and not r['cache_validacao'][comp]['hit'] for r in rows),
                   'tempo_original_reutilizado_s':math.fsum(r.get('cache_validacao',{}).get(comp,{}).get('duracao_original_s',0)
                                                          for r in rows if r.get('cache_validacao',{}).get(comp,{}).get('hit'))}
            for comp in ('sast','funcional')}
    return resultado


DIMENSOES={'estrategia':'estrategia_curta','caso':'caso_id','cwe':'cwe_ids','owasp':'owasp_2025',
           'severidade':'severidade','regra':'check_id','auditoria':'classificacao_auditoria',
           'rag_original':'categoria_rag','rag_recuperada':'rag_categoria_recuperada'}


def calcular(entrada, definicao_principal='criterio', pesos=None):
    import json
    from pipeline.metrics import VERSAO
    rows=entrada.linhas
    groups=defaultdict(list)
    for row in rows:
        groups[(row['dry_run'],row['caso_id'])].append(row)
    for case_rows in groups.values():
        stopped=False
        for row in case_rows:
            if row['condicao']=='diagnostico':continue
            row['pos_aceite']=stopped
            if row['classificacao_original']=='aceita':stopped=True
    populations={name:[] for name in ('real_desenho','dry_run_desenho','real_diagnostico','dry_run_diagnostico')}
    for row in rows:
        if row['pos_aceite']:continue
        name=('dry_run' if row['dry_run'] else 'real')+'_'+row['condicao']
        populations[name].append(row)
    aggregate={};summary={}
    for name,ls in populations.items():
        summary[name]={'tentativas':len(ls),'casos_alcancados':len({l['caso_id'] for l in ls}),
            'indeterminadas_sast':sum(any(l.get('classificacao_'+d)=='indeterminada_sast' for d in DEFS) for l in ls),
            'R_M_nao_medidos':sum(l.get('R') is None or l.get('M') is None for l in ls),
            'nao_aplicadas':sum(l['status_aplicacao']!='aplicado' for l in ls),
            'falhas_tecnicas':sum(str(l.get('classificacao_original','')).startswith(('erro','falha_tecnica')) for l in ls),
            'definicoes':{d:{'metricas':metricas(ls,d,entrada.catalogo.ampliado,pesos),
                             'F_nao_medido':sum(l.get('F_'+d) is None for l in ls),
                             'normalizacao_incompleta':sum(l.get('incompleto_'+d,False) for l in ls)} for d in DEFS}}
        aggregate[name]={}
        for dim,field in DIMENSOES.items():
            by=defaultdict(list)
            for l in ls:
                value=l.get(field)
                if dim=='cwe' and not value:value=None
                by[json.dumps(value,ensure_ascii=False,sort_keys=True)].append(l)
            aggregate[name][dim]=[{'grupo':json.loads(key),'tentativas':len(sub),
                                   'casos_alcancados':len({l['caso_id'] for l in sub}),
                                   'definicoes':{d:metricas(sub,d,entrada.catalogo.ampliado,pesos) for d in DEFS}}
                                  for key,sub in sorted(by.items())]
    requested=entrada.contrato['casos'] if entrada.contrato else None
    observed=sorted({l['caso_id'] for l in rows if l['condicao']=='desenho'})
    case_ids=sorted(requested if requested is not None else observed)
    requested_strategies=entrada.contrato['estrategias'] if entrada.contrato else None
    cases=[]
    for cid in case_ids:
        ls=[l for l in rows if l['caso_id']==cid and l['condicao']=='desenho' and not l['pos_aceite']]
        accepts=[l for l in ls if l['classificacao_original']=='aceita']
        state=('aceito' if accepts else 'pendente' if requested_strategies is not None and
               set(requested_strategies)-{l['estrategia_curta'] for l in ls} else 'sem_aceite' if ls else 'sem_tentativa')
        if requested is None and not accepts:state='sem_aceite_observado'
        cases.append({'caso_id':cid,'status':state,'iniciado':bool(ls),'estrategia_aceite_original':accepts[0]['estrategia_curta'] if accepts else None,
                      'estrategias_observadas':[l['estrategia_curta'] for l in ls],
                      'definicoes':{d:any(l['status_aplicacao']=='aplicado' and (l.get('R'),l.get('F_'+d),l.get('M'))==(1,1,1) for l in ls) for d in DEFS}})
    case_metrics={}
    for sim,pop in ((False,'real_desenho'),(True,'dry_run_desenho')):
        active=populations[pop];observed_set={l['caso_id'] for l in active}
        case_metrics[pop]={}
        for d in DEFS:
            accepted={l['caso_id'] for l in active if l['status_aplicacao']=='aplicado' and (l.get('R'),l.get('F_'+d),l.get('M'))==(1,1,1)}
            relevant=entrada.contrato and ((entrada.contrato['modo']=='dry-run') == sim) and entrada.contrato['modo']!='preflight'
            case_metrics[pop][d]={'CR':metrica(len(accepted),len(requested),'casos_solicitados') if relevant else indisponivel('conjunto_solicitado_indisponivel'),
                                  'TRV_caso_observado':metrica(len(accepted),len(observed_set),'casos_observados')}
    return {'schema_versao':VERSAO,'execucao':entrada.execucao,
            'status':'sem_tentativas' if entrada.preflight is not None else 'consolidado',
            'catalogo_tipo':entrada.catalogo.tipo,'definicao_f_principal':definicao_principal,
            'politicas':{'calculo':'metricas_v1','normalizacao':'historica_preservada_v1','cadeia':'aceite_original_coorte_fixa_v1',
                        'taxas_ampliadas':'somente_medidos','cwe':'conjunto_composto_sem_sobreposicao'},
            'populacoes':summary,'agregacoes':aggregate,'metricas_por_caso':case_metrics,'casos':cases,
            'cobertura':{'solicitados':len(requested) if requested is not None else None,'iniciados':sum(c['iniciado'] for c in cases),
                         'estados':dict(Counter(c['status'] for c in cases)),'pos_aceite':sum(l['pos_aceite'] for l in rows)},
            'preparacao':{'casos':entrada.preflight['casos'],'prompts':len(entrada.preflight['prompts']),'tentativas':0} if entrada.preflight else None,
            'custos_tempos':custos_atual(rows,entrada.sessoes),'RRIS':indisponivel('evidencia_conjunta_ausente'),
            'proveniencia':{'nivel':'verificada' if entrada.catalogo.ampliado else 'historica_limitada','fontes_sha256':dict(sorted(entrada.fontes.items()))},
            'avisos':entrada.avisos+['As estratégias alcançam populações diferentes; taxas não demonstram efeito causal.',
                      'TCD é exploratório; falha de teste D não confirma bloqueio do ataque.',
                      'Contagens de indisponibilidade podem se sobrepor.']}
