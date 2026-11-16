"""Fallback por deslocamento uniforme de recuo, restrito a JS/TS com AST local."""
from __future__ import annotations
from pathlib import Path
import subprocess

from pipeline.etapas.e01_analise_sast import estrutura

EXTENSOES = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}


def linhas(texto):
    result=[]
    for raw in texto.splitlines(keepends=True):
        eol='\r\n' if raw.endswith('\r\n') else '\n' if raw.endswith('\n') else ''
        result.append((raw[:-len(eol)] if eol else raw,eol))
    return result


def deslocamento(original, real):
    shift=None
    for (a,_),(b,_) in zip(original,real):
        if a.lstrip(' \t')!=b.lstrip(' \t'):return None
        if not a.strip(' \t'):continue
        ai=a[:len(a)-len(a.lstrip(' \t'))];bi=b[:len(b)-len(b.lstrip(' \t'))]
        if bi.endswith(ai):current=('adicionar',bi[:len(bi)-len(ai)] if ai else bi)
        elif ai.endswith(bi):current=('remover',ai[:len(ai)-len(bi)] if bi else ai)
        else:return None
        if shift is not None and current!=shift:return None
        shift=current
    # Mesmo recuo também permite conferir diferenças LF/CRLF, sem normalizar conteúdo.
    return shift or ('adicionar','')


def tokens_equivalentes(arquivo, antes, depois, checkout):
    try:
        data=estrutura.analisar(arquivo,antes.encode('utf-8'),depois.encode('utf-8'),checkout)
        return ([t['texto'] for t in data['antes']['tokens']]
                == [t['texto'] for t in data['depois']['tokens']])
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        # Sem parser confiável, não há aproximação textual automática.
        return False


def localizar(conteudo, original):
    """Retorna todos os blocos completos com mesmo conteúdo e recuo uniforme."""
    anchor=linhas(original);source=linhas(conteudo)
    if len(anchor)<2 or not any(body.strip(' \t') for body,_ in anchor):return []
    offsets=[];offset=0
    for body,eol in source:offsets.append(offset);offset+=len(body)+len(eol)
    matches=[]
    for start in range(len(source)-len(anchor)+1):
        block=source[start:start+len(anchor)]
        shift=deslocamento(anchor,block)
        if shift is None:continue
        if anchor[-1][1] and not block[-1][1]:continue
        ends={eol for _,eol in block if eol}
        if len(ends)>1:continue
        eol=next(iter(ends),'\n')
        begin=offsets[start]
        end=offsets[start+len(anchor)-1]+len(block[-1][0])+(len(block[-1][1]) if anchor[-1][1] else 0)
        matches.append({'inicio':begin,'fim':end,'linha_inicio':start+1,
                        'linha_fim':start+len(anchor),'deslocamento':shift,'eol':eol})
    return matches


def ajustar(texto, shift, eol):
    mode,prefix=shift;out=[]
    for body,ending in linhas(texto):
        if body.strip(' \t'):
            if mode=='adicionar':body=prefix+body
            elif body.startswith(prefix):body=body[len(prefix):]
            else:return None
        out.append(body+(eol if ending else ''))
    return ''.join(out)


def resolver(arquivo, conteudo, original, corrigido, checkout):
    if Path(arquivo).suffix.lower() not in EXTENSOES:return None,'linguagem_sem_fallback'
    matches=localizar(conteudo,original)
    if len(matches)>1:return None,'ancora_ambigua'
    if not matches:return None,'ancora_nao_encontrada'
    match=matches[0];begin,end=match['inicio'],match['fim'];eol=match['eol']
    raw_original=original
    raw_new=corrigido
    shifted=ajustar(corrigido,match['deslocamento'],eol)
    if shifted is None:return None,'recuo_corrigido_incompativel'
    def replace(value):return conteudo[:begin]+value+conteudo[end:]
    # A primeira comparação protege o código original (templates, strings e regex).
    # A segunda impede que o recuo altere valores literais da solução proposta.
    if not tokens_equivalentes(arquivo,conteudo,replace(raw_original),checkout):
        return None,'normalizacao_original_insegura'
    if not tokens_equivalentes(arquivo,replace(raw_new),replace(shifted),checkout):
        return None,'normalizacao_correcao_insegura'
    return (replace(shifted),match),'indentacao_uniforme'
