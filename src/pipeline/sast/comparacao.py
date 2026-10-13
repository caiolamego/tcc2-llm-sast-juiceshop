"""Comparação conservadora de ocorrências após patches, com cobertura explícita."""
from __future__ import annotations
from collections import defaultdict, Counter
from difflib import SequenceMatcher
import hashlib
import json

VERSAO = 'blocos_unicos_v1'


def chave(f):
    return (f.check_id, f.path, f.start_line, f.start_col, f.end_line, f.end_col)


def chave_caso(c):
    return (c['check_id'], c['arquivo'], c['linha_inicio'], c['coluna_inicio'], c['linha_fim'], c['coluna_fim'])


def gate(catalogo, scan):
    expected, actual = Counter(chave_caso(c) for c in catalogo.casos), Counter(chave(f) for f in scan.findings)
    return {'reproduzido':expected == actual and not scan.falha_operacional,
            'ausentes':[list(k) for k in sorted((expected-actual).elements())],
            'adicionais':[list(k) for k in sorted((actual-expected).elements())],
            'catalogo_qtd':sum(expected.values()), 'scan_qtd':sum(actual.values()),
            'falha_operacional':scan.falha_operacional,'diagnosticos':scan.diagnosticos}


def ocorrencias(seq, block):
    n = len(block)
    return sum(seq[i:i+n] == block for i in range(len(seq)-n+1))


def blocos_unicos(antes: bytes, depois: bytes):
    a,b = antes.decode('utf-8').splitlines(keepends=True),depois.decode('utf-8').splitlines(keepends=True)
    blocks=[]
    for block in SequenceMatcher(None,a,b,autojunk=False).get_matching_blocks():
        if block.size and ocorrencias(a,a[block.a:block.a+block.size]) == 1 and ocorrencias(b,a[block.a:block.a+block.size]) == 1:
            blocks.append((block.a+1, block.b+1, block.size))
    return blocks


def id_posterior(f):
    return hashlib.sha256(json.dumps(chave(f),separators=(',',':')).encode()).hexdigest()


def comparar(antes, depois, alvo: tuple, fontes: dict[str, tuple[bytes,bytes]]):
    groups=defaultdict(lambda:[[],[]])
    for i,f in enumerate(antes.findings): groups[(f.check_id,f.path)][0].append((i,f))
    for i,f in enumerate(depois.findings): groups[(f.check_id,f.path)][1].append((i,f))
    pares, removidos, novos, ambiguos, blocks_report = [],[],[],[],{}
    for (rule,path),(a,b) in sorted(groups.items()):
        blocks = blocos_unicos(*fontes[path]) if path in fontes else None
        if blocks is not None: blocks_report[path]=blocks
        paired_a, paired_b = set(),set()
        proposals=[]
        for ia,f in a:
            target = chave(f)
            if blocks is not None:
                matched=[(old,new,n) for old,new,n in blocks if old<=f.start_line<=f.end_line<old+n]
                if len(matched)!=1: continue
                old,new,_=matched[0]
                target=(rule,path,f.start_line+new-old,f.start_col,f.end_line+new-old,f.end_col)
            candidates=[ib for ib,g in b if chave(g)==target]
            if len(candidates)==1: proposals.append((ia,candidates[0]))
        counts=Counter(ib for _,ib in proposals)
        for ia,ib in proposals:
            if counts[ib]==1:
                paired_a.add(ia);paired_b.add(ib)
                fa=next(f for i,f in a if i==ia);fb=next(f for i,f in b if i==ib)
                pares.append({'antes':list(chave(fa)),'depois':list(chave(fb))})
        left_a=[list(chave(f)) for i,f in a if i not in paired_a]
        left_b=[list(chave(f)) for i,f in b if i not in paired_b]
        if left_a and left_b: ambiguos.append({'regra':rule,'arquivo':path,'antes':left_a,'depois':left_b})
        else: removidos+=left_a;novos+=left_b
    old_errors=Counter(json.dumps(e,sort_keys=True) for e in antes.diagnosticos)
    limited,affected = [],set()
    for e in depois.diagnosticos:
        p=e.get('path')
        sig=json.dumps(e,sort_keys=True)
        if p and p not in fontes and old_errors[sig]>0:
            limited.append(e);old_errors[sig]-=1
        else: affected.add(p or '*')
    # Um erro antigo em arquivo alterado não pode ser apagado silenciosamente pelo scan posterior.
    for e in antes.diagnosticos:
        if e.get('path') in fontes: affected.add(e['path'])
    operational=antes.falha_operacional or depois.falha_operacional
    if operational: affected.add('*')
    alvo_list=list(alvo)
    r = 0 if any(p['antes']==alvo_list for p in pares) else 1 if alvo_list in removidos else None
    if '*' in affected or alvo[1] in affected or any(e.get('path') == alvo[1] for e in antes.diagnosticos + depois.diagnosticos): r=None
    # Só é comprovadamente novo se a análise anterior desse arquivo também estava completa.
    old_error_paths={e.get('path') or '*' for e in antes.diagnosticos}
    confirmed_new=[k for k in novos if k[1] not in affected and '*' not in affected and k[1] not in old_error_paths and '*' not in old_error_paths]
    uncertain_new=[k for k in novos if k not in confirmed_new]
    m=0 if confirmed_new else None if ambiguos or affected or uncertain_new else 1
    return {'versao_comparador':VERSAO,'R':r,'M':m,'pares':pares,'removidos':removidos,
            'novos':confirmed_new,'possiveis_novos':uncertain_new,
            'ambiguos':ambiguos,'blocos':blocks_report,'cobertura_limitada':limited,
            'arquivos_inconclusivos':sorted(affected),'falha_operacional':operational,
            'diagnosticos_antes':antes.diagnosticos,'diagnosticos_depois':depois.diagnosticos,
            'novas_issues_qtd':len(confirmed_new),
            'possiveis_novas_issues_qtd':len(uncertain_new)+sum(len(g['depois']) for g in ambiguos),
            'comparacao_status':'indeterminada' if r is None or m is None else 'conclusiva'}
