#!/usr/bin/env python3
"""Compara replays concluídos sem executar serviços, testes, patches ou LLM."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402

import argparse
import csv
import io
import json
import math
import os
import re
import shutil
import statistics
import tempfile

from pipeline.etapas.e09_metricas.publicacao import _promover_exclusivo, json_bytes
from pipeline.comum.identidade import digest


def carregar(base, nomes):
    fontes, runs = {}, []
    base = Path(base).resolve()
    def ler(path):
        path=path.resolve()
        if not path.is_relative_to(base):raise ValueError('Entrada fora da raiz do benchmark')
        fontes[str(path.relative_to(base))]=digest(path)
        return json.loads(path.read_text())
    for nome in nomes:
        if not re.fullmatch(r'[A-Za-z0-9_-]+',nome):raise ValueError('Nome de execução inválido')
        root=base/nome
        manifest=ler(root/'manifesto.json');rows=ler(root/'resultados.json')
        if (manifest.get('tipo')!='benchmark_replay_sem_llm' or manifest.get('status')!='concluido'
                or manifest.get('chamadas_llm')!=0 or not manifest.get('limpas') or manifest.get('erros')):
            raise ValueError(f'Benchmark incompleto ou com falhas: {nome}')
        if manifest.get('observacoes')!=len(rows) or not rows:
            raise ValueError('Contagem de observações divergente')
        if type(manifest.get('tempo_parede_execucao_s')) not in (int,float) or not math.isfinite(manifest['tempo_parede_execucao_s']) or manifest['tempo_parede_execucao_s']<=0:
            raise ValueError('Tempo de execução inválido')
        vistos=set()
        for row in rows:
            ident=(row['caso_id'],row['estrategia'],row['repeticao'])
            if ident in vistos:raise ValueError('Observação duplicada')
            vistos.add(ident)
            rid=row['replay_id']
            if not re.fullmatch(r'[A-Za-z0-9_-]+',rid):raise ValueError('ID de replay inválido')
            pasta=root/'tentativas'/rid
            comp=ler(pasta/'comparacao.json');val=ler(pasta/'validacao.json')
            if any(comp[k]!=row[k] for k in ('R','M')) or any(val['F_'+d]!=row['F_'+d] for d in ('criterio','marcador','sem_separacao')):
                raise ValueError('Resultado divergente das evidências')
            for path in sorted(pasta.iterdir()):
                if path.is_file():fontes[str(path.resolve().relative_to(base))]=digest(path)
            evidencia=pasta/'sast_raw_evidencia_funcional.json'
            if not evidencia.is_file() or digest(evidencia)!=row['cache_validacao']['funcional']['evidencia_sha256']:
                raise ValueError('Evidência funcional reutilizável adulterada/ausente')
        runs.append({'nome':nome,'manifesto':manifest,'rows':rows})
    return runs,fontes


def comparar(runs, referencia):
    referencia=next((r for r in runs if r['nome']==referencia),None)
    if not referencia:raise ValueError('Referência ausente')
    def indice(run):return {(r['caso_id'],r['estrategia'],r['repeticao']):r for r in run['rows']}
    ref=indice(referencia);diferencas=[];resumos=[];grupos={}
    for run in runs:
        atual=indice(run)
        if set(ref)!=set(atual):raise ValueError('Populações de patches diferentes entre replays')
        if run['manifesto']['commit_alvo']!=referencia['manifesto']['commit_alvo']:
            raise ValueError('Commits diferentes no benchmark')
        if run['manifesto']['validacao']['implementacao']!=referencia['manifesto']['validacao']['implementacao']:
            raise ValueError('Implementações diferentes; não agrupar medições')
        for key,row in atual.items():
            if row['patch_sha256']!=ref[key]['patch_sha256']:raise ValueError('Patches diferentes')
            for campo in ('R','M','F_criterio','F_marcador','F_sem_separacao','falhas_persistentes','falhas_intermitentes'):
                observado = sorted(row[campo]) if isinstance(row[campo],list) else row[campo]
                esperado = sorted(ref[key][campo]) if isinstance(ref[key][campo],list) else ref[key][campo]
                if observado!=esperado:
                    diferencas.append({'execucao':run['nome'],'caso':key[0],'estrategia':key[1],
                                       'campo':campo,'referencia':ref[key][campo],'observado':row[campo]})
        m=run['manifesto']
        resumo={'execucao':run['nome'],'politica':m['validacao']['politica_validacao'],
                'k':m['k'],'tempo_parede_s':m['tempo_parede_execucao_s'],'preparacao_s':m['preparacao_s'],
                'observacoes':len(atual),'pico_rss_kib':m.get('pico_rss_descendentes_kib'),
                'reusos_sast':sum(r['cache_validacao']['sast']['hit'] for r in atual.values()),
                'reusos_funcionais':sum(r['cache_validacao']['funcional']['hit'] for r in atual.values())}
        resumos.append(resumo)
        grupo=re.sub(r'_V[0-9]+$','',re.sub(r'^R[0-9]+_','',run['nome']))
        grupos.setdefault(grupo,[]).append(resumo)
    estatisticas=[]
    for grupo,rows in sorted(grupos.items()):
        valores=[r['tempo_parede_s'] for r in rows]
        estatisticas.append({'cenario':grupo,'repeticoes':len(rows),'mediana_s':statistics.median(valores),
                             'minimo_s':min(valores),'maximo_s':max(valores),
                             'observacoes':sum(r['observacoes'] for r in rows)})
    estat={r['cenario']:r for r in estatisticas}
    ganhos=[]
    for origem,destino in (('REF_K1','OPT_FRIO_K1'),('OPT_FRIO_K1','OPT_FRIO_K2')):
        if origem not in estat or destino not in estat:continue
        a,b=estat[origem],estat[destino]
        ganho=a['mediana_s']/b['mediana_s']
        ganhos.append({'referencia':origem,'candidato':destino,'razao_mediana':ganho,
                       'economia_percentual':100*(1-1/ganho),
                       'tres_repeticoes':min(a['repeticoes'],b['repeticoes'])>=3})
    return {'schema_versao':'1.0','tipo':'comparacao_replay_sem_llm','chamadas_llm':0,
            'referencia':referencia['nome'],'execucoes':resumos,'estatisticas':estatisticas,
            'comparacoes_tempo':ganhos,'divergencias':diferencas,
            'limites':['Replays não são novas correções ou réplicas independentes de LLM.',
                       'Cache quente mede reutilização, não nova medição de qualidade.',
                       'Resultados de oito patches não garantem cobertura dos 78 casos.',
                       'Pico de RSS amostrado soma páginas potencialmente compartilhadas.']}


def publicar(saida, report, base, fontes):
    saida=Path(saida).resolve()
    if saida.exists():raise ValueError('Destino já existe')
    if any((base/nome.split('/')[0]).resolve().is_relative_to(saida) or
           saida.is_relative_to((base/nome.split('/')[0]).resolve()) for nome in fontes):
        raise ValueError('Saída sobreposta às entradas')
    saida.parent.mkdir(parents=True,exist_ok=True)
    lock=saida.with_name(saida.name+'.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    tmp=None
    try:
        tmp=Path(tempfile.mkdtemp(prefix=saida.name+'.tmp-',dir=saida.parent))
        (tmp/'comparacao.json').write_bytes(json_bytes(report))
        columns=['execucao','politica','k','tempo_parede_s','preparacao_s','observacoes','pico_rss_kib','reusos_sast','reusos_funcionais']
        with (tmp/'tempos.csv').open('w',encoding='utf-8',newline='') as stream:
            w=csv.DictWriter(stream,columns);w.writeheader();w.writerows(report['execucoes'])
        texto=['# Comparação da validação sem LLM','','| Cenário | Repetições | Mediana | Intervalo |','|---|---:|---:|---:|']
        for r in report['estatisticas']:
            texto.append(f"| {r['cenario']} | {r['repeticoes']} | {r['mediana_s']:.3f} s | {r['minimo_s']:.3f}–{r['maximo_s']:.3f} s |")
        texto += ['',f"Divergências de resultados/evidências: {len(report['divergencias'])}.",'',*report['limites']]
        (tmp/'RESUMO.md').write_text('\n'.join(texto)+'\n',encoding='utf-8')
        for nome,old in fontes.items():
            if digest(base/nome)!=old:raise ValueError('Entrada alterada durante consolidação')
        manifesto={'schema_versao':'1.0','fontes_sha256':fontes,
                   'artefatos_sha256':{p.name:digest(p) for p in sorted(tmp.iterdir())}}
        (tmp/'manifesto.json').write_bytes(json_bytes(manifesto))
        _promover_exclusivo(tmp,saida)
    finally:
        if tmp and tmp.exists():shutil.rmtree(tmp)
        os.close(fd);lock.unlink()


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--entrada',type=Path,required=True)
    ap.add_argument('--execucoes',required=True,help='Nomes separados por vírgula; excluir smoke tests preliminares')
    ap.add_argument('--referencia',default='R1_REF_K1')
    ap.add_argument('--saida',type=Path,required=True)
    args=ap.parse_args(argv)
    try:
        nomes=args.execucoes.split(',')
        if len(set(nomes))!=len(nomes):raise ValueError('Execução duplicada')
        runs,fontes=carregar(args.entrada,nomes)
        publicar(args.saida,comparar(runs,args.referencia),args.entrada.resolve(),fontes)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(f'ERRO: {exc}',file=sys.stderr);return 1
    print(f'Comparação publicada em {args.saida}');return 0


if __name__=='__main__':raise SystemExit(main())
