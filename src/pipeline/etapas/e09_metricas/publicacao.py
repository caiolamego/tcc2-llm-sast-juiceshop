"""Artefatos determinísticos e publicação exclusiva em destino novo."""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

from pipeline.etapas.e09_metricas import exigir
from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e09_metricas.normalizacao import DEFS


def _numeros(data):
    if isinstance(data,float):
        exigir(math.isfinite(data),'Número de saída inválido')
        return round(data,6)
    if isinstance(data,dict):return {k:_numeros(v) for k,v in data.items()}
    if isinstance(data,list):return [_numeros(v) for v in data]
    return data


def json_bytes(data):
    return (json.dumps(_numeros(data),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')


def csv_bytes(columns, rows):
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=columns,lineterminator='\n')
    writer.writeheader()
    for row in rows:
        values={}
        for k in columns:
            v=row.get(k)
            if isinstance(v,(dict,list)):v=json.dumps(_numeros(v),ensure_ascii=False,sort_keys=True,separators=(',',':'))
            elif isinstance(v,float):v=round(v,6)
            elif isinstance(v,bool):v='true' if v else 'false'
            values[k]=v
        writer.writerow(values)
    return buf.getvalue().encode('utf-8')


COL_AGG=['execucao','populacao','definicao_f','grupo','metrica','valor','numerador','denominador','politica','status','motivo']
BASE_ROW=['tentativa_id','caso_id','condicao','estrategia_curta','dry_run','do_cache','pos_aceite','inferencias_historicas',
          'arquivo','check_id','cwe_ids','owasp_2025','severidade','classificacao_auditoria','categoria_rag',
          'rag_categoria_recuperada','rag_motivo_recuperacao','rag_cwe_selecionada','arquivo_rag_recuperado',
          'rag_documento_versao','rag_documento_sha256','rag_corpo_sha256','rag_index_sha256','rag_base_sha256',
          'status_aplicacao','classificacao_original','R','F','M','R_original','F_original','M_original',
          'tier_falha','custo_usd','tokens_entrada','tokens_saida','duracao_llm_s','duracao_sast_s','duracao_validacao_s']
COL_ROW=BASE_ROW+[key for d in DEFS for key in (f'F_{d}',f'F_{d}_original',f'classificacao_{d}',f'classificacao_{d}_original',f'incompleto_{d}')]


def _metric_rows(ex, pop, d, group, values):
    return [{'execucao':ex,'populacao':pop,'definicao_f':d,'grupo':group,'metrica':m,**v} for m,v in sorted(values.items())]


def construir(report, entrada):
    artifacts={'metricas.json':json_bytes(report)}
    colunas = list(COL_ROW)
    if entrada.contrato and entrada.contrato.get('schema_versao') in ('3.0','4.0','5.0'):
        colunas += ['politica_validacao','cache_validacao','tempos_medicao','selecao_testes','etapas_validacao']
        if (entrada.contrato['schema_versao']=='4.0' or entrada.contrato['schema_versao']=='5.0' and entrada.contrato.get('contrato_validacao_versao')=='4.0'):colunas+=['cobertura_funcional','cobertura_detalhada']
    if entrada.contrato and entrada.contrato.get('schema_versao')=='5.0':
        colunas += ['provedor','identidade_inferencia','custo_motivo','custo_api_usd','custo_infraestrutura_usd','espera_inferencia_s','requisicao_s','chamadas_enviadas','estado_geracao']
    rows=[]
    for l in entrada.linhas:
        row={k:l.get(k) for k in colunas}
        for k in ('R','F','M',*(f'F_{d}' for d in DEFS),*(f'classificacao_{d}' for d in DEFS)):
            row[k+'_original']=l['original'].get(k)
        rows.append(row)
    artifacts['tentativas.csv']=csv_bytes(colunas,rows)
    cases=[]
    for c in report['casos']:
        cases.append({**{k:v for k,v in c.items() if k!='definicoes'},**{f'aceito_{d}':c['definicoes'][d] for d in DEFS}})
    artifacts['casos.csv']=csv_bytes(['caso_id','status','iniciado','estrategia_aceite_original','estrategias_observadas',*(f'aceito_{d}' for d in DEFS)],cases)
    general=[]
    for pop,summary in report['populacoes'].items():
        for d in DEFS:
            general+=_metric_rows(report['execucao'],pop,d,None,summary['definicoes'][d]['metricas'])
    for pop,ds in report['metricas_por_caso'].items():
        for d,values in ds.items():general+=_metric_rows(report['execucao'],pop,d,None,values)
    general+=_metric_rows(report['execucao'],'conjunto',report['definicao_f_principal'],None,{'RRIS':report['RRIS']})
    artifacts['metricas_gerais.csv']=csv_bytes(COL_AGG,general)
    dims={'estrategia':'estrategia','caso':'caso','cwe':'cwe','owasp':'owasp','severidade':'severidade','regra':'regra','auditoria':'auditoria'}
    if entrada.contrato and entrada.contrato.get('schema_versao')=='5.0':dims['inferencia']='inferencia'
    for suffix,dim in dims.items():
        agg=[]
        for pop,dimensions in report['agregacoes'].items():
            for item in dimensions[dim]:
                for d in DEFS:agg+=_metric_rows(report['execucao'],pop,d,item['grupo'],item['definicoes'][d])
        artifacts['metricas_por_'+suffix+'.csv']=csv_bytes(COL_AGG,agg)
    rag=[]
    for pop,dimensions in report['agregacoes'].items():
        for dim in ('rag_original','rag_recuperada'):
            for item in dimensions[dim]:
                for d in DEFS:
                    rag += [{**row,'dimensao':dim} for row in _metric_rows(report['execucao'],pop,d,item['grupo'],item['definicoes'][d])]
    artifacts['metricas_por_rag.csv']=csv_bytes(['dimensao',*COL_AGG],rag)
    if entrada.contrato and (entrada.contrato.get('schema_versao')=='4.0' or entrada.contrato.get('schema_versao')=='5.0' and entrada.contrato.get('contrato_validacao_versao')=='4.0'):
        coverage=[]
        for pop,dimensions in report['agregacoes'].items():
            for item in dimensions['cobertura_funcional']:
                for d in DEFS:coverage+=_metric_rows(report['execucao'],pop,d,item['grupo'],item['definicoes'][d])
        artifacts['metricas_por_cobertura_funcional.csv']=csv_bytes(COL_AGG,coverage)
    manifest={'schema_versao':'1.0','execucao':report['execucao'],'fontes_sha256':dict(sorted(entrada.fontes.items())),
              'politicas':report['politicas'],'definicao_f_principal':report['definicao_f_principal'],
              'artefatos_sha256':{name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(artifacts.items())}}
    artifacts['manifesto.json']=json_bytes(manifest)
    return artifacts


def _promover_exclusivo(origem, destino):
    """renameat2 impede substituir até um diretório vazio criado no último instante."""
    import ctypes
    import errno
    import sys
    if sys.platform.startswith('linux'):
        libc=ctypes.CDLL(None,use_errno=True)
        rename=getattr(libc,'renameat2',None)
        if rename is None:raise OSError(errno.ENOTSUP,'Promoção exclusiva indisponível')
        rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
        rename.restype=ctypes.c_int
        if rename(-100,os.fsencode(origem),-100,os.fsencode(destino),1):
            error=ctypes.get_errno();raise OSError(error,os.strerror(error),str(destino))
    elif os.name=='nt':
        os.rename(origem,destino)  # Windows já recusa destino existente.
    else:
        raise OSError(errno.ENOTSUP,'Sistema sem promoção exclusiva suportada')


def publicar(destino, artifacts, entrada):
    destino=Path(destino).absolute()
    resolved=destino.resolve()
    exigir(not destino.exists() and not destino.is_symlink(),'Destino existente; use uma saída nova')
    roots=[entrada.raiz,entrada.catalogo.caminho.parent,RAIZ_REPO/'workspace',RAIZ_REPO/'config',RAIZ_REPO/'rules',RAIZ_REPO/'knowledge_base']
    roots += [RAIZ_REPO/'outputs'/n for n in ('sast_antes','resultados_consolidados','catalogos','auditoria_sast','feature01','feature02','feature03')]
    exigir(resolved!=RAIZ_REPO and resolved!=RAIZ_REPO/'outputs' and all(not resolved.is_relative_to(r.resolve()) and not r.resolve().is_relative_to(resolved) for r in roots),'Saída sobreposta a entradas/evidências protegidas')
    exigir(all(not p.is_relative_to(resolved) for p in entrada.arquivos),'Saída sobreposta a fonte')
    destino.parent.mkdir(parents=True,exist_ok=True)
    lock=destino.with_name(destino.name+'.lock');temp=None;owner=False
    try:
        try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError as exc:raise ValueError(f'Lock existente: {lock.name}; investigue a execução proprietária antes de remover manualmente') from exc
        owner=True
        with os.fdopen(fd,'w') as f:f.write(str(os.getpid())+'\n')
        exigir(not destino.exists() and not destino.is_symlink(),'Destino criado por outra execução')
        temp=Path(tempfile.mkdtemp(prefix='.'+destino.name+'-',dir=destino.parent))
        for name,raw in sorted(artifacts.items()):
            exigir(Path(name).name==name,'Nome de artefato inválido')
            (temp/name).write_bytes(raw)
        entrada.revalidar()
        exigir(not destino.exists() and not destino.is_symlink(),'Destino criado durante geração')
        _promover_exclusivo(temp,destino);temp=None
    finally:
        if temp is not None:shutil.rmtree(temp)
        if owner:lock.unlink(missing_ok=True)
