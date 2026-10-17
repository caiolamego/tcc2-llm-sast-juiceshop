#!/usr/bin/env python3
"""Compara uma revalidação sem LLM com os registros originais, sem alterá-los."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: E402,F401
import argparse
from collections import Counter
import json

from pipeline.caminhos import RAIZ_REPO
from pipeline.metrics.loader import carregar
from pipeline.metrics.exporter import json_bytes,csv_bytes
from pipeline.validation.coverage_audit import publicar
from pipeline.validation.identity import digest
from pipeline.validation.selection import interno


def classificacao(r):
    if r['F_criterio'] is None:return 'indeterminada_funcional'
    if r['R'] is None or r['M'] is None:return 'indeterminada_sast'
    if (r['R'],r['F_criterio'],r['M'])==(1,1,1):return 'aceita'
    return f"rejeitada:R{r['R']}F{r['F_criterio']}M{r['M']}"


def comparar(origem,replay,catalogo):
    origem,replay=Path(origem).resolve(),Path(replay).resolve()
    original=json.loads((origem/'contrato_execucao.json').read_text())
    entrada=carregar(origem,original['execucao'],catalogo)
    inputs=dict(entrada.arquivos)
    inputs[Path(__file__).resolve()]=digest(__file__)
    def ler(p):
        inputs[p]=digest(p)
        return json.loads(p.read_text())
    manifest=ler(replay/'manifesto.json')
    if (manifest.get('tipo')!='revalidacao_patches_sem_llm' or manifest.get('status')!='concluido'
            or manifest.get('chamadas_llm')!=0 or manifest.get('origem_execucao')!=entrada.execucao
            or manifest.get('repeticoes')!=1):
        raise ValueError('Revalidação incompleta ou incompatível')
    novos=ler(replay/'resultados.json');by={r['replay_id']:r for r in novos}
    if len(by)!=len(novos):raise ValueError('Replay duplicado')
    esperado={r['tentativa_id']+'_REP1' for r in entrada.linhas if r['artefatos'].get('patch')}
    if set(by)!=esperado:raise ValueError('População de patches divergente')
    rows=[];ops_originais=0;ops_atuais=0
    for old in entrada.linhas:
        ident=old['tentativa_id'];new=by.get(ident+'_REP1')
        r={'tentativa_id':ident,'caso_id':old['caso_id'],'arquivo':old['arquivo'],
           'estrategia':old['estrategia_curta'],'status':'revalidado' if new else 'sem_patch',
           'classificacao_original':old['classificacao_final'],
           **{k+'_original':old.get(k) for k in ('R','M','F_sem_separacao','F_marcador','F_criterio')}}
        if new:
            patch=interno(RAIZ_REPO,old['artefatos']['patch'])
            if new['patch_sha256']!=digest(patch):raise ValueError('Patch diferente da origem')
            folder=interno(replay,'tentativas/'+new['replay_id'])
            comp=ler(folder/'comparacao.json');val=ler(folder/'validacao.json')
            if any(comp[k]!=new[k] for k in ('R','M')) or any(val[k]!=new[k] for k in ('F_sem_separacao','F_marcador','F_criterio')):
                raise ValueError('Resultados divergentes das evidências')
            for artifact in folder.iterdir():
                if artifact.is_file():inputs[artifact]=digest(artifact)
            evidence=folder/'sast_raw_evidencia_funcional.json'
            if digest(evidence)!=new['cache_validacao']['funcional']['evidencia_sha256']:
                raise ValueError('Evidência funcional adulterada')
            original_invalid=bool((old.get('cobertura_detalhada') or {}).get('motivos'))
            invalid=any(g['falha_operacional'] for g in val['cobertura_detalhada']['grupos'])
            ops_originais+=original_invalid;ops_atuais+=invalid
            r.update({k+'_revalidado':new[k] for k in ('R','M','F_sem_separacao','F_marcador','F_criterio')})
            r.update(classificacao_revalidada=classificacao(new),patch_sha256=digest(patch),
                     falha_operacional_original=original_invalid,falha_operacional_revalidada=invalid,
                     motivos=val['cobertura_detalhada']['motivos'],falhos_funcionais=val['testes_falhos_f_criterio'],
                     falhos_desafios=val['testes_falhos_d_criterio'],worktree=new['worktree'],tempo_revalidacao_s=new['total_s'])
        rows.append(r)
    rows.sort(key=lambda r:r['tentativa_id'])
    medidos=[r for r in rows if r['status']=='revalidado']
    summary={'schema_versao':'1.0','tipo':'diagnostico_revalidacao_sem_llm','origem_execucao':entrada.execucao,
             'registros_originais':len(rows),'patches_revalidados':len(medidos),'sem_patch':len(rows)-len(medidos),
             'classificacoes_originais':dict(Counter(r['classificacao_original'] for r in rows)),
             'classificacoes_revalidadas':dict(Counter(r['classificacao_revalidada'] for r in medidos)),
             'casos_com_patch_aceito':sorted({r['caso_id'] for r in medidos if r['classificacao_revalidada']=='aceita'}),
             'F_criterio_alterados':sum(r['F_criterio_original']!=r['F_criterio_revalidado'] for r in medidos),
             'R_M_alterados':sum(any(r[k+'_original']!=r[k+'_revalidado'] for k in ('R','M')) for r in medidos),
             'falhas_operacionais_originais':ops_originais,'falhas_operacionais_revalidadas':ops_atuais,
             'chamadas_llm':0,'tempo_replay_s':manifest['tempo_parede_execucao_s'],
             'limite':'Replay dos mesmos patches; não são novas tentativas LLM, nem efeito causal das estratégias. Nenhuma taxa histórica foi substituída.'}
    artifacts={'comparacao.json':json_bytes(rows),'resumo.json':json_bytes(summary),
               'comparacao.csv':csv_bytes(sorted({k for r in rows for k in r}),rows)}
    artifacts['manifesto.json']=json_bytes({'schema_versao':'1.0',
        'fontes_sha256':{str(p.relative_to(RAIZ_REPO)):h for p,h in sorted(inputs.items())},
        'artefatos_sha256':{n:__import__('hashlib').sha256(b).hexdigest() for n,b in sorted(artifacts.items())}})
    entrada.revalidar()
    return artifacts,inputs,summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('origem','replay','catalogo','saida'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        artifacts,inputs,summary=comparar(args.origem,args.replay,args.catalogo)
        publicar(args.saida,artifacts,inputs)
        print(json.dumps(summary,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError) as exc:print(str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
