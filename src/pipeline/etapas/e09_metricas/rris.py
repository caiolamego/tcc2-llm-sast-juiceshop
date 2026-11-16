"""Leitor de evidência conjunta: não aplica patches nem executa scans."""
import math
from pathlib import Path
from collections import Counter

from pipeline.etapas.e09_metricas import exigir, digest, ler_json, relativo
from pipeline.etapas.e09_metricas.calculo import metrica, indisponivel


def carregar_pesos(path, entrada):
    if path is None:return None
    path=Path(path).resolve();data=ler_json(path)
    exigir(data.get('schema_versao')=='1.0' and isinstance(data.get('versao'),str),'Schema/versão dos pesos inválidos')
    weights=data.get('pesos');aliases=data.get('aliases',{})
    exigir(isinstance(weights,dict) and bool(weights) and isinstance(aliases,dict),'Política de pesos inválida')
    exigir(all(isinstance(k,str) and type(v) in (int,float) and math.isfinite(v) and v>0 for k,v in weights.items()),'Pesos devem ser finitos e positivos')
    result=dict(weights)
    for alias,target in aliases.items():
        exigir(isinstance(alias,str) and isinstance(target,str) and target in weights and alias not in weights,'Alias de severidade inválido')
        result[alias]=weights[target]
    entrada.registrar(path,'politica_pesos.json')
    return result


def _artefato(manifest, key, root, entrada):
    item=manifest.get(key)
    exigir(isinstance(item,dict) and isinstance(item.get('sha256'),str),'Referência de evidência inválida')
    file=relativo(root,item.get('arquivo'))
    exigir(digest(file)==item['sha256'],'Hash de evidência conjunta adulterado')
    entrada.registrar(file,'rris/'+key)
    return file


def _scan(path, perfil):
    data=ler_json(path)
    exigir(data.get('version')==perfil.dados['semgrep_versao'],'Versão de scan RRIS incompatível')
    results=data.get('results');errors=data.get('errors',[])
    exigir(isinstance(results,list) and isinstance(errors,list),'Scan RRIS inválido')
    ids=set(perfil.dados['id_regras']);findings=[]
    for r in results:
        file=r.get('path');p=Path(file) if isinstance(file,str) else Path('/')
        exigir(isinstance(file,str) and not p.is_absolute() and '..' not in p.parts and '\\' not in file,'Scan RRIS requer caminhos relativos normalizados')
        exigir(r.get('check_id') in ids,'Regra RRIS ausente no perfil')
        if not perfil.no_escopo(file):continue
        start=r.get('start',{});end=r.get('end',{})
        coords=[start.get('line'),start.get('col'),end.get('line'),end.get('col')]
        exigir(all(type(n) is int and n>0 for n in coords) and tuple(coords[:2])<=tuple(coords[2:]),'Coordenadas RRIS inválidas')
        findings.append((r['check_id'],file,*coords))
    diagnostics=[]
    for error in errors:
        exigir(isinstance(error,dict), 'Diagnóstico RRIS inválido')
        file=error.get('path') or error.get('location',{}).get('path')
        if file is not None:
            p=Path(file)
            exigir(not p.is_absolute() and '..' not in p.parts, 'Diagnóstico RRIS deve ser relativo')
            if not perfil.no_escopo(file):continue
        diagnostics.append({'path':file,'type':error.get('type'),'message':error.get('message')})
    return findings,diagnostics,data.get('falha_operacional')


def calcular_rris(path, entrada, definicao):
    import json
    if path is None:return indisponivel('evidencia_conjunta_ausente')
    exigir(entrada.contrato is not None and entrada.contrato['modo']=='real','RRIS exige execução real com contrato')
    path=Path(path).resolve();root=path.parent;data=ler_json(path)
    entrada.registrar(path,'rris/manifesto.json')
    exigir(data.get('schema_versao')=='1.0' and data.get('execucao')==entrada.execucao,'Schema/execução RRIS incompatível')
    exigir(data.get('commit_baseline')==entrada.catalogo.commit and data.get('hashes_catalogo')==entrada.catalogo.hashes and
           data.get('perfil_sha256')==entrada.contrato['perfil_sha256'] and data.get('definicao_f')==definicao,'Contrato científico RRIS incompatível')
    patches=data.get('patches');order=data.get('ordem_aplicacao');conflicts=data.get('conflitos');not_applied=data.get('nao_aplicadas')
    exigir(isinstance(patches,list) and bool(patches) and isinstance(order,list) and isinstance(conflicts,list) and isinstance(not_applied,list),'Seleção/ordem/conflitos RRIS inválidos')
    rows={r['tentativa_id']:r for r in entrada.linhas};selected=[];changed=set()
    for i,item in enumerate(patches):
        tid=item.get('tentativa_id');row=rows.get(tid)
        exigir(row is not None and not row['dry_run'] and not row['pos_aceite'] and row['condicao']=='desenho' and
               row['status_aplicacao']=='aplicado' and (row.get('R'),row.get('F_'+definicao),row.get('M'))==(1,1,1),'Patch RRIS sem aceite comprovado')
        exigir(tid not in selected,'Patch RRIS duplicado');selected.append(tid)
        patch_path=_artefato({'patch':item},'patch',root,entrada)
        # Papel único para múltiplos patches no mapa de proveniência.
        entrada.fontes.pop('rris/patch',None)
        entrada.fontes[f'rris/patch/{tid}']=digest(patch_path)
        ledger=row['original'].get('artefatos_sha256',{})
        reference=row['original'].get('artefatos',{}).get('patch')
        matches=[h for f,h in ledger.items() if reference==f or isinstance(reference,str) and reference.endswith('/'+f)]
        exigir(len(matches)==1 and matches[0]==item['sha256'],'Patch RRIS diverge do patch aceito')
        files=row.get('arquivos_alterados',[])
        exigir(isinstance(files,list) and bool(files),'Patch RRIS sem arquivos alterados')
        for file in files:
            p=Path(file);exigir(not p.is_absolute() and '..' not in p.parts,'Arquivo alterado RRIS inválido');changed.add(file)
    exigir(order==selected,'Ordem RRIS não corresponde aos patches efetivamente aplicados')
    exigir(all(isinstance(c,dict) and c.get('tentativa_id') in rows for c in conflicts),'Conflito RRIS inválido')
    exigir(all(isinstance(t,str) and t in rows and t not in selected for t in not_applied),'Tentativas RRIS não aplicadas inválidas')
    exigir(all(c['tentativa_id'] in not_applied for c in conflicts),'Conflito não registrado como não aplicado')
    profile_path=_artefato(data,'perfil',root,entrada)
    exigir(digest(profile_path)==data['perfil_sha256'],'Perfil RRIS divergente')
    from pipeline.etapas.e01_analise_sast.perfil import carregar
    profile_data=ler_json(profile_path)
    for config in profile_data.get('configs',[]):
        file=relativo(profile_path.parent,config['arquivo']);entrada.registrar(file,'rris/regras/'+config['arquivo'])
    profile=carregar(profile_path)
    before_path=_artefato(data,'scan_antes',root,entrada);after_path=_artefato(data,'scan_depois',root,entrada)
    functional_path=_artefato(data,'validacao_funcional',root,entrada)
    functional=ler_json(functional_path)
    exigir(type(functional.get('passou')) is bool,'Resultado funcional conjunto inválido')
    before,errors_before,fail_before=_scan(before_path,profile)
    after,errors_after,fail_after=_scan(after_path,profile)
    old=Counter(json.dumps(e,sort_keys=True) for e in errors_before);limited=[];uncertain=[]
    for e in errors_after:
        sig=json.dumps(e,sort_keys=True)
        if e['path'] and e['path'] not in changed and old[sig]>0:
            old[sig]-=1;limited.append(e)
        else:uncertain.append(e)
    # Aviso antigo desaparecido ou arquivo alterado não demonstra análise comparável.
    for e in errors_before:
        if e['path'] in changed or old[json.dumps(e,sort_keys=True)]>0:uncertain.append(e)
    timeout=any('timeout' in str(e.get('type','')).lower() for e in errors_before+errors_after)
    status=indisponivel('comparabilidade_sast_indeterminada') if uncertain or fail_before or fail_after or timeout else metrica(len(before)-len(after),len(before),'findings_globais_conjunto')
    status.update(I_antes=len(before),I_depois=len(after),patches_aplicados=selected,nao_aplicadas=not_applied,
                  conflitos=conflicts,cobertura_limitada=limited,diagnosticos_indeterminados=uncertain,
                  conjunto_funcionalmente_validado=functional['passou'])
    if status['valor'] is not None and not functional['passou']:
        status['interpretacao']='Redução estática comparável; conjunto não validado funcionalmente.'
    return status
