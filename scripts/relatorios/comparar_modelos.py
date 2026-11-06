#!/usr/bin/env python3
"""Compara execuções de modelos diferentes a partir das métricas já publicadas.

Só lê as pastas <EXECUCAO> e <EXECUCAO>_METRICAS. As comparações são pareadas:
usam os casos e as estratégias em comum, porque a cadeia P1 a P4 faz cada
estratégia ser medida sobre casos diferentes.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
import itertools
import json
from math import comb

csv.field_size_limit(sys.maxsize)  # tentativas.csv guarda listas longas de testes.
METRICAS=('TRV','TAP','TRI','TPF','TNINI','TFF','TCD')
ESTRATEGIAS=('P1','P2','P3','P4')


def ler_csv(path):
    with open(path,encoding='utf-8',newline='') as stream:
        return list(csv.DictReader(stream))


def escrever_csv(path, linhas, campos):
    with open(path,'w',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=campos,lineterminator='\n');w.writeheader();w.writerows(linhas)


def mcnemar_exato(so_a, so_b):
    """Valor-p bilateral do teste exato sobre os pares discordantes."""
    n=so_a+so_b
    if n==0:return 1.0
    return min(1.0,2*sum(comb(n,k) for k in range(min(so_a,so_b)+1))/2**n)


def sim(valor):
    return str(valor).strip().lower() in ('1','true','sim')


def origem_regra(check_id):
    return 'regra_propria' if str(check_id).startswith('tcc.') else 'registro'


def carregar(pasta, definicao):
    pasta=Path(pasta);m=Path(str(pasta)+'_METRICAS')
    contrato=json.loads((pasta/'contrato_execucao.json').read_text(encoding='utf-8'))
    modelo=(contrato.get('inferencia') or {}).get('modelo') or 'desconhecido'
    tentativas=ler_csv(m/'tentativas.csv');casos=ler_csv(m/'casos.csv')
    rel=json.loads((m/'metricas.json').read_text(encoding='utf-8'))
    gerais={r['metrica']:r for r in ler_csv(m/'metricas_gerais.csv') if r['populacao']=='real_desenho' and r['definicao_f']==definicao}
    estrategia=[r for r in ler_csv(m/'metricas_por_estrategia.csv') if r['populacao']=='real_desenho' and r['definicao_f']==definicao]
    return {'pasta':pasta,'modelo':modelo,'tentativas':tentativas,'casos':casos,'rel':rel,'gerais':gerais,'estrategia':estrategia,
            'aceitos':{c['caso_id'] for c in casos if sim(c.get('aceito_'+definicao))},
            'fontes':[m/n for n in ('tentativas.csv','casos.csv','metricas.json','metricas_gerais.csv','metricas_por_estrategia.csv')]}


def linha_geral(e, definicao):
    pop=e['rel']['populacoes']['real_desenho'];custo=e['rel']['custos_tempos']['custo_usd']
    horas=sum(s.get('duracao_s') or 0 for s in e['rel']['custos_tempos']['duracoes_sessoes'])/3600
    cr=e['rel']['metricas_por_caso']['real_desenho'][definicao]['CR']
    linha={'modelo':e['modelo'],'execucao':e['pasta'].name,'tentativas':pop['tentativas'],'casos_solicitados':cr.get('denominador'),
           'casos_aceitos':cr.get('numerador'),'CR':cr.get('valor'),'custo_usd':custo.get('total_conhecido'),'horas':round(horas,2)}
    for nome in METRICAS:
        g=e['gerais'].get(nome,{});linha[nome]=g.get('valor','');linha[nome+'_n']=f"{g.get('numerador','')}/{g.get('denominador','')}"
    return linha


def por_grupo(e):
    """Taxa de casos aceitos por atributo do caso, sem contar tentativas repetidas."""
    atributos={}
    for t in e['tentativas']:
        atributos.setdefault(t['caso_id'],t)
    grupos=defaultdict(lambda:[0,0])
    for caso,t in atributos.items():
        chaves=[('auditoria',t['classificacao_auditoria']),('origem_regra',origem_regra(t['check_id']))]
        chaves+=[('cwe',c) for c in str(t['cwe_ids']).replace(';',',').replace('|',',').split(',') if c.strip()]
        for chave in chaves:
            grupos[chave][1]+=1;grupos[chave][0]+=caso in e['aceitos']
    return [{'modelo':e['modelo'],'dimensao':d,'grupo':g,'aceitos':a,'casos':n,'taxa':round(a/n,4)} for (d,g),(a,n) in sorted(grupos.items())]


def pareado_modelos(execucoes):
    linhas=[]
    for a,b in itertools.combinations(execucoes,2):
        comuns={c['caso_id'] for c in a['casos']}&{c['caso_id'] for c in b['casos']}
        so_a=len((a['aceitos']-b['aceitos'])&comuns);so_b=len((b['aceitos']-a['aceitos'])&comuns)
        ambos=len(a['aceitos']&b['aceitos']&comuns)
        linhas.append({'modelo_a':a['modelo'],'modelo_b':b['modelo'],'casos_comuns':len(comuns),'ambos':ambos,'so_a':so_a,'so_b':so_b,
                       'nenhum':len(comuns)-ambos-so_a-so_b,'p_mcnemar_exato':round(mcnemar_exato(so_a,so_b),4)})
    return linhas


def pareado_estrategias(e, definicao):
    """Usa todas as tentativas do desenho, inclusive as feitas depois de um aceite."""
    aceitas=defaultdict(dict)
    for t in e['tentativas']:
        if t['condicao']=='desenho' and t['estrategia_curta'] in ESTRATEGIAS:
            aceitas[t['estrategia_curta']][t['caso_id']]=t.get('classificacao_'+definicao)=='aceita'
    linhas=[]
    for a,b in itertools.combinations(ESTRATEGIAS,2):
        comuns=set(aceitas[a])&set(aceitas[b])
        so_a=sum(aceitas[a][c] and not aceitas[b][c] for c in comuns);so_b=sum(aceitas[b][c] and not aceitas[a][c] for c in comuns)
        ambos=sum(aceitas[a][c] and aceitas[b][c] for c in comuns)
        linhas.append({'modelo':e['modelo'],'estrategia_a':a,'estrategia_b':b,'casos_comuns':len(comuns),'ambos':ambos,'so_a':so_a,'so_b':so_b,
                       'nenhum':len(comuns)-ambos-so_a-so_b,'p_mcnemar_exato':round(mcnemar_exato(so_a,so_b),4)})
    return linhas


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execucoes',nargs='+',type=Path,required=True,help='Pastas das execuções, uma por modelo')
    ap.add_argument('--saida',type=Path,required=True)
    ap.add_argument('--definicao-f',choices=('criterio','marcador','sem_separacao'),default='criterio')
    args=ap.parse_args()
    d=args.definicao_f
    try:
        execucoes=[carregar(p,d) for p in args.execucoes]
        modelos=[e['modelo'] for e in execucoes]
        if len(set(modelos))!=len(modelos):
            raise ValueError('Cada execução deve ser de um modelo diferente: '+', '.join(modelos))
        args.saida.mkdir(parents=True,exist_ok=False)
        geral=[linha_geral(e,d) for e in execucoes]
        escrever_csv(args.saida/'modelos_geral.csv',geral,list(geral[0]))
        campos=('modelo','grupo','metrica','valor','numerador','denominador','status')
        escrever_csv(args.saida/'modelos_estrategia.csv',[{'modelo':e['modelo'],**{c:r.get(c,'') for c in campos[1:]}} for e in execucoes for r in e['estrategia'] if r['metrica'] in METRICAS],campos)
        grupos=[l for e in execucoes for l in por_grupo(e)]
        escrever_csv(args.saida/'modelos_grupos.csv',grupos,['modelo','dimensao','grupo','aceitos','casos','taxa'])
        pm=pareado_modelos(execucoes)
        if pm:escrever_csv(args.saida/'pareado_modelos.csv',pm,list(pm[0]))
        pe=[l for e in execucoes for l in pareado_estrategias(e,d)]
        escrever_csv(args.saida/'pareado_estrategias.csv',pe,list(pe[0]))
        fontes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for e in execucoes for p in e['fontes']}
        (args.saida/'manifesto.json').write_text(json.dumps({'schema_versao':'1.0','definicao_f':d,'modelos':modelos,'fontes_sha256':fontes,
            'nota':'Valores-p sem correção para comparações múltiplas; nenhuma comparação entre modelos usa a RRIS.'},ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    except (ValueError,OSError,KeyError,TypeError) as exc:
        ap.exit(1,f'ERRO: {exc}\n')
    for g in geral:print(g['modelo'],'| casos aceitos',g['casos_aceitos'],'de',g['casos_solicitados'],'| TRV',g['TRV'],g['TRV_n'],'| US$',g['custo_usd'])


if __name__=='__main__':raise SystemExit(main())
