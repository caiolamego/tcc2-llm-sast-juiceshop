"""Cálculos conhecidos, proveniência e publicação; nenhuma rede/execução do alvo."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
import copy
import csv
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.etapas.e09_metricas import digest, relativo
from pipeline.etapas.e09_metricas.leitura import carregar, Entrada
from pipeline.etapas.e09_metricas.normalizacao import normalizar_atual
from pipeline.etapas.e09_metricas.calculo import calcular, metricas, custos_atual
from pipeline.etapas.e09_metricas.publicacao import construir, publicar, json_bytes, csv_bytes
from pipeline.etapas.e09_metricas.rris import carregar_pesos, calcular_rris
from scripts.auditoria.congelar_perfil_sast import construir as build_profile
from scripts.relatorios import metricas_historicas as legacy


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(json_bytes(data))


def case(cid='JS001',file='a.ts'):
    return {'caso_id':cid,'arquivo':file,'linha_inicio':1,'linha_fim':1,'check_id':'r.remote',
            'assinatura':cid+'sig','cwe':['CWE-89: SQL'],'cwe_ids':['CWE-89'], 'owasp_2025':None,
            'severidade':'INFO','categoria_rag':'injection','classificacao_auditoria':'falso_positivo'}


def row(c=None,e='P1',R=1,F=1,M=1,applied=True,dry=False):
    c=c or case();accepted=applied and (R,F,M)==(1,1,1)
    label='aceita' if accepted else 'indeterminada_sast' if R is None or M is None else 'rejeitada'
    if not applied:label='nao_aplicada:fixture'
    return {'tentativa_id':f'{c["caso_id"]}_SEM_OWASP_OUTRO_{e}_TEST_UNDERSCORES','execucao':'TEST',
            'caso_id':c['caso_id'],'arquivo':c['arquivo'],'check_id':c['check_id'],'linha':1,
            'assinatura':c['assinatura'],'estrategia_prompt':{'P1':'P1_simples','P2':'P2_raciocinio_guiado','P1L':'P1L_diagnostico_localizacao'}[e],
            'condicao':'diagnostico' if e=='P1L' else 'desenho','R':R,'F':F,'M':M,
            **{f'F_{d}':F for d in legacy.DEFS},**{f'classificacao_{d}':label for d in legacy.DEFS},
            'classificacao_final':label,'status_aplicacao':'aplicado' if applied else 'fixture_nao_aplicado',
            'dry_run':dry,'modelo':'dry-run' if dry else 'fixture','do_cache':False,'custo_usd':0 if dry else 0.2,
            'tokens_entrada':10,'tokens_saida':5,'duracao_llm_s':2,'duracao_sast_s':1,'duracao_validacao_s':3,
            'testes_falhos_d_criterio':[],'testes_falhos_d_marcador':[],'tier_falha':None,'artefatos':{},'sigla_vuln':'OUTRO'}


def context(root, rows, cases=None, ampliado=True, requested=None):
    cases=cases or [case(r['caso_id'],r['arquivo']) for r in rows]
    by={c['caso_id']:c for c in cases}
    catalog=SimpleNamespace(ampliado=ampliado,tipo='ampliado' if ampliado else 'historico',casos=list(by.values()),
                            caminho=root/'catalog/catalogo_issues.json',commit='a'*40,hashes={'catalogo':'fixture'})
    contract={'casos':requested if requested is not None else sorted(by),'estrategias':['P1','P2'],
              'modo':'dry-run' if rows and rows[0]['dry_run'] else 'real','perfil_sha256':'fixture'} if ampliado else None
    return Entrada(root/'input','TEST',catalog,contract,[normalizar_atual(r,by[r['caso_id']],r['estrategia_prompt'].split('_')[0]) for r in rows],[],None)


def historic(root, rows=None):
    c=case();rows=rows if rows is not None else [row(c)]
    inp=root/'input';cat=root/'catalog/catalogo_issues.json';save(cat,[c])
    file=inp/'resultados_consolidados/execucoes.jsonl';file.parent.mkdir(parents=True)
    file.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    return inp,cat,file


def expanded(root, mode='real'):
    from pipeline.etapas.e02_catalogo.catalogo import carregar as load_catalog
    inp=root/'input';prof=inp/'perfil_sast';source=root/'rules';source.mkdir(parents=True)
    remote=root/'remote.yaml';remote.write_text('rules:\n- id: r.remote\n  languages: [javascript]\n  pattern: x\n  message: m\n  severity: INFO\n')
    (source/'local.yaml').write_text(remote.read_text().replace('r.remote','tcc.local'))
    exclude=root/'exclude';exclude.write_text('test/\n')
    artifacts=build_profile(remote,source,exclude);prof.mkdir(parents=True)
    for name,raw in artifacts.items():(prof/name).write_bytes(raw)
    c=case();sig=hashlib.sha256(json.dumps(['a'*40,'r.remote','a.ts',1,1,1,2],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    c.update(caso_id='AMP'+sig[:16],assinatura_ocorrencia=sig,commit_alvo='a'*40,coluna_inicio=1,coluna_fim=2,elegivel=True)
    c.pop('assinatura')
    cat=root/'catalog/catalogo_issues.json';save(cat,[c]);excluded=cat.parent/'exclusoes.json';save(excluded,[])
    meta={'schema_versao':'1.0','politica_versao':'escopo_apenas_v1','catalogo_tipo':'ampliado_por_ocorrencia','commit_alvo':'a'*40,
          'fontes':{},'contagens':{'casos_incluidos':1,'alertas_excluidos':0,'alertas_brutos':1,'por_classificacao':{'falso_positivo':1}},
          'artefatos':{'catalogo_issues.json':digest(cat),'exclusoes.json':digest(excluded)}}
    save(cat.parent/'catalogo_meta.json',meta);catalog=load_catalog(cat)
    contract={'schema_versao':'2.0','execucao':'TEST','modo':mode,'commit_alvo':c['commit_alvo'],
              'hashes_catalogo':catalog.hashes,'casos':[c['caso_id']],'estrategias':['P1'],'diagnosticos':[],
              'perfil_sha256':digest(prof/'perfil.json'),'semgrep_versao':'1.177.0','comparador':'blocos_unicos_v1'}
    contract_path=inp/'contrato_execucao.json';save(contract_path,contract)
    raw=inp/'sast_antes/baseline_raw.json';save(raw,{'version':'1.177.0','results':[{'check_id':'r.remote','path':'a.ts','start':{'line':1,'col':1},'end':{'line':1,'col':2}}]})
    gate={'reproduzido':True,'contrato_execucao_sha256':digest(contract_path),'baseline_sha256':digest(raw)}
    save(inp/'sast_antes/reproducao.json',gate)
    if mode=='preflight':
        messages=[{'role':'user','content':'fixture'}];h=hashlib.sha256(json.dumps(messages,ensure_ascii=False).encode()).hexdigest()
        save(inp/f'prompts/{c["caso_id"]}_P1.json',{'estrategia':'P1_simples','mensagens':messages,'hash_prompt':h})
        save(inp/'preflight.json',{'status':'concluido','casos':1,'contrato_execucao_sha256':digest(contract_path),'custo_api_usd':0,'prompts':[{'caso':c['caso_id'],'estrategia':'P1','hash_prompt':h}]})
        return inp,cat,c,None
    r=row({**c,'assinatura':'unused'},dry=mode=='dry-run');r.pop('assinatura');r['assinatura_ocorrencia']=c['assinatura_ocorrencia']
    r.update(commit_alvo=c['commit_alvo'],hashes_catalogo=catalog.hashes,contrato_execucao_sha256=digest(contract_path),perfil_sha256=contract['perfil_sha256'],arquivos_alterados=['a.ts'])
    artifact=inp/'patches/patch.diff';artifact.parent.mkdir();artifact.write_text('fixture patch\n')
    r['artefatos']={'patch':'portable/old/root/patches/patch.diff'};r['artefatos_sha256']={'patches/patch.diff':digest(artifact)}
    file=inp/'resultados_consolidados/execucoes.jsonl';file.parent.mkdir();file.write_text(json.dumps(r)+'\n')
    return inp,cat,c,r


class NumerosTests(unittest.TestCase):
    def test_v4_keeps_different_functional_scopes_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=case('AMP_A'),case('AMP_B')
            entry=context(Path(folder),[row(a),row(b)])
            entry.contrato['schema_versao']='4.0'
            for record,group in zip(entry.linhas,['login','key']):
                record['cobertura_detalhada']={'dominios':['api'],'grupos_selecionados':[group],'suficiente':True}
                record['cobertura_funcional']='relacionada_v2'
            report=calcular(entry)
            groups=report['agregacoes']['real_desenho']['cobertura_funcional']
            self.assertEqual(len(groups),2)
            self.assertEqual({tuple(g['grupo']['grupos']) for g in groups},{('login',),('key',)})
            self.assertEqual(report['populacoes']['real_desenho']['tentativas'],2)
            entry.contrato.pop('schema_versao')
            self.assertNotIn('cobertura_funcional',calcular(entry)['agregacoes']['real_desenho'])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_four_known_results(self):
        rows=[row(case('JS001')),row(case('JS002'),R=0),row(case('JS003'),R=None,F=0,M=None),row(case('JS004'),R=None,F=None,M=None,applied=False)]
        ent=context(self.root,rows);m=metricas(ent.linhas,'criterio',True)
        for key,expected in {'TRV':1/4,'TAP':3/4,'TRI':1/2,'TPF':2/3,'TFF':1/3,'TNINI':1,'TRI_minima':1/4,'TPF_minima':1/2,'TNINI_minima':1/2}.items():self.assertAlmostEqual(m[key]['valor'],expected)
        self.assertEqual(m['TPF']['denominador'],3)
        self.assertEqual(ent.linhas[3]['F_criterio'],None)

    def test_historical_denominator_and_empty(self):
        r=normalizar_atual(row(R=None,F=None,M=None),case(),'P1')
        self.assertIsNone(metricas([r],'criterio',True)['TPF']['valor'])
        self.assertEqual(metricas([r],'criterio',False)['TPF']['valor'],0)
        for v in metricas([],'criterio',True).values():self.assertIsNone(v['valor'])

    def test_populations_cache_and_original_stop_fixed_for_sensitivity(self):
        c=case();a=row(c);b=row(c,'P2');diag=row(c,'P1L');a['do_cache']=True
        a['F_marcador']=0;a['classificacao_marcador']='rejeitada'  # Aceite original conserva coorte.
        ent=context(self.root,[a,b,diag]);report=calcular(ent)
        self.assertEqual(report['populacoes']['real_desenho']['tentativas'],1)
        self.assertEqual(report['populacoes']['real_diagnostico']['tentativas'],1)
        self.assertEqual(report['cobertura']['pos_aceite'],1)
        self.assertEqual(report['custos_tempos']['chamadas_novas_registradas'],2)
        self.assertEqual(report['custos_tempos']['usos_cache'],1)
        self.assertEqual(report['populacoes']['real_desenho']['definicoes']['marcador']['metricas']['TRV']['valor'],0)

    def test_cr_requested_and_pending(self):
        cases=[case('JS00'+str(i)) for i in range(1,6)]
        ent=context(self.root,[row(cases[0]),row(cases[1]),row(cases[2],R=0),row(cases[3],R=0)],cases,requested=[c['caso_id'] for c in cases])
        report=calcular(ent)
        self.assertEqual(report['metricas_por_caso']['real_desenho']['criterio']['CR']['valor'],2/5)
        self.assertEqual(report['cobertura']['iniciados'],4)
        self.assertEqual(report['casos'][4]['status'],'pendente')

    def test_complete_no_accept_and_historic_coverage(self):
        c=case();ent=context(self.root,[row(c,R=0),row(c,'P2',R=0)])
        self.assertEqual(calcular(ent)['casos'][0]['status'],'sem_aceite')
        ent=context(self.root,[row(c)],ampliado=False)
        self.assertIsNone(calcular(ent)['metricas_por_caso']['real_desenho']['criterio']['CR']['valor'])

    def test_dry_run_not_real(self):
        ent=context(self.root,[row(case('JS001'),R=0,dry=True),row(case('JS002'),R=0,F=0,dry=True)])
        result=calcular(ent);m=result['populacoes']['dry_run_desenho']['definicoes']['criterio']['metricas']
        self.assertEqual([m[k]['valor'] for k in ['TRV','TRI','TPF','TFF','TNINI','TAP']],[0,0,.5,.5,1,1])
        self.assertIsNone(result['populacoes']['real_desenho']['definicoes']['criterio']['metricas']['TRV']['valor'])
        self.assertEqual(result['custos_tempos']['custo_usd']['total_conhecido'],0)

    def test_cost_unknown_cache_and_parallel_time(self):
        a=row();b=row(case('JS002'));b['do_cache']=True;b['custo_usd']=1000;a['custo_usd']=None
        ls=[normalizar_atual(a,case(),'P1'),normalizar_atual(b,case('JS002'),'P1')]
        data=custos_atual(ls,[{'duracao_s':3,'erros':[{'erro':'fixture'}]}])
        self.assertEqual(data['custo_usd']['ausentes'],1);self.assertEqual(data['custo_usd']['completude'],'parcial')
        self.assertEqual(data['duracoes_sessoes'][0]['duracao_s'],3)
        self.assertEqual(data['tempos_acumulados']['duracao_validacao_s']['total_conhecido'],6)
        ls[0]['tokens_entrada']=-1
        with self.assertRaises(ValueError):custos_atual(ls,[])

    def test_missing_metadata_multi_cwe_no_duplicates(self):
        c=case();c.update(cwe_ids=['CWE-943','CWE-89','CWE-89'],owasp_2025=None)
        ent=context(self.root,[row(c)],cases=[c]);report=calcular(ent)
        agg=report['agregacoes']['real_desenho']
        self.assertEqual(agg['cwe'][0]['grupo'],['CWE-89','CWE-943'])
        self.assertEqual(agg['cwe'][0]['tentativas'],1);self.assertIsNone(agg['owasp'][0]['grupo'])
        self.assertEqual(agg['auditoria'][0]['grupo'],'falso_positivo')

    def test_null_cwe_metadata_and_invalid_ids(self):
        c=case();c.update(cwe=None,cwe_ids=None)
        self.assertEqual(normalizar_atual(row(c),c,'P1')['cwe_ids'],[])
        c['cwe_ids']='CWE-89'
        with self.assertRaises(ValueError):normalizar_atual(row(),c,'P1')

    def test_weights_optional_and_invalid(self):
        ent=context(self.root,[row()]);path=self.root/'pesos.json'
        self.assertIsNone(metricas(ent.linhas,'criterio',True)['TRV-P']['valor'])
        save(path,{'schema_versao':'1.0','versao':'1.0','pesos':{'LOW':2},'aliases':{'INFO':'LOW'}})
        weights=carregar_pesos(path,ent);self.assertEqual(metricas(ent.linhas,'criterio',True,weights)['TRV-P']['valor'],1)
        self.assertIsNone(metricas(ent.linhas,'criterio',True,{'HIGH':1})['TRV-P']['valor'])
        for value in [0,-1,True,'x',float('inf')]:
            path.write_text(json.dumps({'schema_versao':'1.0','versao':'1.0','pesos':{'INFO':value}}))
            with self.assertRaises(ValueError):carregar_pesos(path,ent)

    def test_historical_incomplete_and_immutable(self):
        from pipeline.etapas.e07_validacao.conjunto_d import _lista
        # Falha conhecida em D, antes de T4, não prova sucesso de camadas ausentes.
        name='test/api/a.test.ts :: suite > fixture'
        a=row();a={k:v for k,v in a.items() if not k.startswith('F_') and not k.startswith('classificacao_')};a['classificacao_final']='rejeitada';a['F']=0;a['tier_falha']='T3';a['testes_falhos_novos']=[name]
        old=copy.deepcopy(a)
        with patch('pipeline.etapas.e09_metricas.normalizacao.classificar',return_value={'d_marcador':[name],'d_criterio':[name],'f_marcador':[],'f_criterio':[]}):
            got=normalizar_atual(a,case(),'P1')
        self.assertEqual(a,old);self.assertTrue(got['incompleto_criterio']);self.assertIsNone(got['F_criterio'])


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_historic_fields_and_missing_artifact(self):
        r=row();r['artefatos']={'prompt':'outputs/fixture-inexistente.json'};inp,cat,_=historic(self.root,[r])
        ent=carregar(inp,'TEST',cat)
        self.assertEqual(ent.linhas[0]['estrategia_curta'],'P1')
        self.assertTrue(any(a.get('tipo')=='artefato_historico_ausente' for a in ent.avisos))

    def test_legacy_strategy_fallback_with_underscores(self):
        r=row();r.pop('estrategia_prompt');inp,cat,_=historic(self.root,[r])
        self.assertEqual(carregar(inp,'TEST',cat).linhas[0]['estrategia_curta'],'P1')

    def test_corruption_other_execution_duplicate_pair(self):
        inp,cat,file=historic(self.root)
        raw=file.read_text();file.write_text(raw+'{broken')
        with self.assertRaisesRegex(ValueError,'corrompido'):carregar(inp,'TEST',cat)
        file.write_text(raw+raw)
        with self.assertRaisesRegex(ValueError,'duplicado'):carregar(inp,'TEST',cat)
        r=json.loads(raw);r['tentativa_id']='DIFFERENT';file.write_text(raw+json.dumps(r)+'\n')
        with self.assertRaisesRegex(ValueError,'Par'):carregar(inp,'TEST',cat)
        r['execucao']='OTHER';file.write_text(raw+json.dumps(r)+'\n')
        self.assertEqual(len(carregar(inp,'TEST',cat).linhas),1)

    def test_invalid_values_strategy_and_identity(self):
        inp,cat,file=historic(self.root);original=json.loads(file.read_text())
        for changes in [{'R':True},{'M':2},{'F':.5},{'estrategia_prompt':'BAD'},{'assinatura':'wrong'},{'caso_id':'ABSENT'},{'condicao':'diagnostico'}]:
            file.write_text(json.dumps({**original,**changes})+'\n')
            with self.assertRaises(ValueError):carregar(inp,'TEST',cat)

    def test_amp_contract_and_ledgers(self):
        inp,cat,c,r=expanded(self.root)
        ent=carregar(inp,'TEST',cat);self.assertEqual(ent.linhas[0]['classificacao_auditoria'],'falso_positivo')
        (inp/'patches/patch.diff').write_text('changed')
        with self.assertRaisesRegex(ValueError,'adulterado'):carregar(inp,'TEST',cat)

    def test_amp_signature_contract_and_accept_contradictions(self):
        inp,cat,c,r=expanded(self.root);file=inp/'resultados_consolidados/execucoes.jsonl'
        for changes in [{'assinatura_ocorrencia':'bad'},{'commit_alvo':'b'*40},{'R':0},{'hashes_catalogo':{}},{'perfil_sha256':'bad'},{'F_criterio':None}]:
            file.write_text(json.dumps({**r,**changes})+'\n')
            with self.assertRaises(ValueError):carregar(inp,'TEST',cat)

    def test_preflight_zero_prompts_verified_and_no_experiment(self):
        inp,cat,_,_=expanded(self.root,'preflight')
        with patch('pipeline.orquestracao.campanha.aplicar',side_effect=AssertionError('patch')),patch('pipeline.orquestracao.campanha.validar',side_effect=AssertionError('F')),patch('pipeline.etapas.e01_analise_sast.semgrep.scan_perfil',side_effect=AssertionError('scan')),patch('pipeline.etapas.e05_geracao_llm.cliente_openai.ConfigLLM.do_env',side_effect=AssertionError('API')):
            ent=carregar(inp,'TEST',cat);report=calcular(ent)
        self.assertEqual(report['preparacao'],{'casos':1,'prompts':1,'tentativas':0})
        self.assertIsNone(report['populacoes']['real_desenho']['definicoes']['criterio']['metricas']['TRV']['valor'])
        p=next((inp/'prompts').glob('*.json'));data=json.loads(p.read_text());data['mensagens'][0]['content']='changed';save(p,data)
        with self.assertRaisesRegex(ValueError,'Hash do prompt'):carregar(inp,'TEST',cat)

    def test_missing_jsonl_and_external_symlinks(self):
        inp,cat,file=historic(self.root);file.unlink()
        with self.assertRaises(ValueError):carregar(inp,'TEST',cat)
        outside=self.root/'outside';outside.write_text(json.dumps(row())+'\n');file.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'Symlink'):carregar(inp,'TEST',cat)

    def test_profile_mutation_rejected(self):
        inp,cat,_,_=expanded(self.root)
        (inp/'perfil_sast/regras_remotas.yaml').write_text('corrupt')
        with self.assertRaisesRegex(ValueError,'adulterado'):carregar(inp,'TEST',cat)

    def test_v1_contract_and_baseline_finding_mismatch(self):
        inp,cat,c,r=expanded(self.root);contract_path=inp/'contrato_execucao.json'
        contract=json.loads(contract_path.read_text());contract['schema_versao']='1.0';save(contract_path,contract)
        r['contrato_execucao_sha256']=digest(contract_path)
        (inp/'resultados_consolidados/execucoes.jsonl').write_text(json.dumps(r)+'\n')
        gate_path=inp/'sast_antes/reproducao.json';gate=json.loads(gate_path.read_text());gate['contrato_execucao_sha256']=digest(contract_path);save(gate_path,gate)
        self.assertEqual(len(carregar(inp,'TEST',cat).linhas),1)
        raw=inp/'sast_antes/baseline_raw.json';data=json.loads(raw.read_text());data['results']=[];save(raw,data)
        gate['baseline_sha256']=digest(raw);save(gate_path,gate)
        with self.assertRaisesRegex(ValueError,'Baseline não corresponde'):carregar(inp,'TEST',cat)

    def test_json_duplicate_key_and_unsafe_ledger(self):
        inp,cat,file=historic(self.root)
        file.write_text('{"execucao":"TEST","execucao":"TEST"}\n')
        with self.assertRaisesRegex(ValueError,'corrompido'):carregar(inp,'TEST',cat)
        other=self.root/'expanded';other.mkdir();inp,cat,c,r=expanded(other)
        r['artefatos_sha256']={'../outside': 'fake'}
        (inp/'resultados_consolidados/execucoes.jsonl').write_text(json.dumps(r)+'\n')
        with self.assertRaisesRegex(ValueError,'externo'):carregar(inp,'TEST',cat)

    def test_snapshot_revalidation(self):
        inp,cat,file=historic(self.root);ent=carregar(inp,'TEST',cat);file.write_text(file.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'alterada'):ent.revalidar()


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_csv_unicode_quotes_null_roundtrip(self):
        data=csv_bytes(['s','n','list'],[{'s':'ação,"texto"\nlinha','n':None,'list':['CWE-89','CWE-943']}])
        parsed=list(csv.DictReader(io.StringIO(data.decode())))[0]
        self.assertEqual(parsed['s'],'ação,"texto"\nlinha');self.assertEqual(parsed['n'],'');self.assertEqual(json.loads(parsed['list']),['CWE-89','CWE-943'])

    def test_new_destination_determinism_and_manifest(self):
        inp,cat,_=historic(self.root);ent=carregar(inp,'TEST',cat);report=calcular(ent);arts=construir(report,ent)
        a=self.root/'reports/a';b=self.root/'reports/b';publicar(a,arts,ent);publicar(b,construir(calcular(ent),ent),ent)
        self.assertEqual({p.name:p.read_bytes() for p in a.iterdir()},{p.name:p.read_bytes() for p in b.iterdir()})
        manifest=json.loads((a/'manifesto.json').read_text())
        self.assertTrue(all(digest(a/name)==h for name,h in manifest['artefatos_sha256'].items()))
        self.assertNotIn(str(self.root),json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'existente'):publicar(a,arts,ent)
        empty=self.root/'empty';empty.mkdir()
        with self.assertRaises(ValueError):publicar(empty,arts,ent)

    def test_locks_failure_and_input_changed_cleanup(self):
        inp,cat,file=historic(self.root);ent=carregar(inp,'TEST',cat);arts=construir(calcular(ent),ent);dest=self.root/'report';lock=self.root/'report.lock';lock.write_text('another')
        with self.assertRaisesRegex(ValueError,'Lock'):publicar(dest,arts,ent)
        self.assertEqual(lock.read_text(),'another');lock.unlink()
        original=Path.write_bytes
        def fail(path,data):
            if path.name=='metricas.json':raise OSError('write failure')
            return original(path,data)
        with patch.object(Path,'write_bytes',fail):
            with self.assertRaises(OSError):publicar(dest,arts,ent)
        self.assertFalse(lock.exists());self.assertFalse(dest.exists());self.assertFalse(list(self.root.glob('.report-*')))
        file.write_text(file.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'alterada'):publicar(dest,arts,ent)
        self.assertFalse(lock.exists());self.assertFalse(dest.exists())

    def test_destination_created_at_promotion_never_overwritten(self):
        from pipeline.etapas.e09_metricas import publicacao
        inp,cat,_=historic(self.root);ent=carregar(inp,'TEST',cat);arts=construir(calcular(ent),ent);dest=self.root/'late'
        original=publicacao._promover_exclusivo
        def competing(src,dst):
            dst.mkdir()
            return original(src,dst)
        with patch.object(publicacao,'_promover_exclusivo',side_effect=competing):
            with self.assertRaises(FileExistsError):publicar(dest,arts,ent)
        self.assertTrue(dest.is_dir());self.assertFalse(list(dest.iterdir()))
        self.assertFalse((self.root/'late.lock').exists());self.assertFalse(list(self.root.glob('.late-*')))

    def test_all_empty_csv_headers_and_record_unknowns(self):
        ent=context(self.root,[]);report=calcular(ent);arts=construir(report,ent)
        for name,data in arts.items():
            if name.endswith('.csv'):self.assertTrue(data.decode().splitlines()[0])
        r=row(R=None,F=None,M=None,applied=False);ent=context(self.root,[r]);arts=construir(calcular(ent),ent)
        parsed=list(csv.DictReader(io.StringIO(arts['tentativas.csv'].decode())))[0]
        self.assertEqual(parsed['R'],'');self.assertEqual(parsed['F_criterio'],'')

    def test_determinism_between_distinct_input_directories(self):
        a=self.root/'a';b=self.root/'b';a.mkdir();b.mkdir()
        inp1,cat1,_=historic(a);inp2,cat2,_=historic(b)
        one=carregar(inp1,'TEST',cat1);two=carregar(inp2,'TEST',cat2)
        self.assertEqual(construir(calcular(one),one),construir(calcular(two),two))

    def test_overlap_rejected(self):
        inp,cat,_=historic(self.root);ent=carregar(inp,'TEST',cat)
        with self.assertRaisesRegex(ValueError,'sobreposta'):publicar(inp/'new',{},ent)

    def test_cli_help_invalid_and_from_other_cwd(self):
        inp,cat,_=historic(self.root);script=ROOT/'scripts/relatorios/consolidar_metricas.py'
        base=[sys.executable,str(script)]
        self.assertEqual(subprocess.run(base+['--help'],cwd=self.root,capture_output=True).returncode,0)
        self.assertEqual(subprocess.run(base,cwd=self.root,capture_output=True).returncode,2)
        cmd=base+['--execucao','TEST','--entrada',str(inp),'--catalogo',str(cat),'--saida',str(self.root/'new')]
        p=subprocess.run(cmd,cwd=self.root,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(subprocess.run(cmd,cwd=self.root,capture_output=True).returncode,1)


class RrisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.inp,self.cat,self.case,self.row=expanded(self.root)
        self.ent=carregar(self.inp,'TEST',self.cat);calcular(self.ent)
        self.evidence=self.root/'joint';self.evidence.mkdir()
        shutil.copytree(self.inp/'perfil_sast',self.evidence/'perfil_sast')
        shutil.copy(self.inp/'patches/patch.diff',self.evidence/'patch.diff')
        self.manifest={'schema_versao':'1.0','execucao':'TEST','commit_baseline':self.ent.catalogo.commit,
            'hashes_catalogo':self.ent.catalogo.hashes,'perfil_sha256':self.ent.contrato['perfil_sha256'],
            'definicao_f':'criterio','patches':[{'tentativa_id':self.row['tentativa_id'],'arquivo':'patch.diff','sha256':digest(self.evidence/'patch.diff')}],
            'ordem_aplicacao':[self.row['tentativa_id']],'conflitos':[],'nao_aplicadas':[]}
        self.path=self.evidence/'manifesto.json'

    def scan(self,n,errors=None,fail=None,path='a.ts'):
        return {'version':'1.177.0','results':[{'check_id':'r.remote','path':path,'start':{'line':i+1,'col':1},'end':{'line':i+1,'col':2}} for i in range(n)],'errors':errors or [],'falha_operacional':fail}

    def publish(self,before,after,passed=True):
        save(self.evidence/'before.json',before);save(self.evidence/'after.json',after);save(self.evidence/'functional.json',{'passou':passed})
        for key,name in [('perfil','perfil_sast/perfil.json'),('scan_antes','before.json'),('scan_depois','after.json'),('validacao_funcional','functional.json')]:
            self.manifest[key]={'arquivo':name,'sha256':digest(self.evidence/name)}
        save(self.path,self.manifest)

    def verificar(self):
        # Nova leitura por cenário; o snapshot de uma consolidação é imutável.
        self.ent=carregar(self.inp,'TEST',self.cat);calcular(self.ent)
        return calcular_rris(self.path,self.ent,'criterio')

    def test_known_joint_ratio_and_multiplicity(self):
        self.publish(self.scan(10),self.scan(7))
        result=self.verificar()
        self.assertEqual(result['valor'],.3);self.assertEqual(result['I_antes'],10)
        self.assertTrue(result['conjunto_funcionalmente_validado'])
        after=self.scan(7);after['results']*=2;self.publish(self.scan(10),after)
        self.assertEqual(self.verificar()['valor'],-.4)

    def test_absent_zero_negative_and_functional_failure(self):
        self.assertIsNone(calcular_rris(None,self.ent,'criterio')['valor'])
        self.publish(self.scan(0),self.scan(0));self.assertIsNone(self.verificar()['valor'])
        self.publish(self.scan(1),self.scan(2),passed=False)
        r=self.verificar();self.assertEqual(r['valor'],-1);self.assertFalse(r['conjunto_funcionalmente_validado']);self.assertIn('não validado',r['interpretacao'])

    def test_parsing_unchanged_limited_changed_new_timeout(self):
        error={'path':'other.ts','type':'Syntax','message':'fixture'}
        self.publish(self.scan(2,[error]),self.scan(1,[error]))
        self.assertEqual(self.verificar()['valor'],.5)
        self.assertEqual(len(self.verificar()['cobertura_limitada']),1)
        for before,after in [(self.scan(2,[dict(error,path='a.ts')]),self.scan(1,[dict(error,path='a.ts')])),
                             (self.scan(2),self.scan(1,[error])),(self.scan(2,[error]),self.scan(1)),
                             (self.scan(2),self.scan(1,fail='timeout'))]:
            self.publish(before,after)
            self.assertIsNone(self.verificar()['valor'])

    def test_bad_hash_profile_contract_patch_or_order_rejected(self):
        self.publish(self.scan(2),self.scan(1));good=copy.deepcopy(self.manifest)
        variants=[dict(good,commit_baseline='b'*40),dict(good,ordem_aplicacao=[]),dict(good,perfil_sha256='bad'),
                  dict(good,patches=[dict(good['patches'][0],sha256='bad')]),dict(good,conflitos=[{'tentativa_id':self.row['tentativa_id']}])]
        for data in variants:
            save(self.path,data)
            with self.assertRaises(ValueError):self.verificar()
        save(self.path,good);(self.evidence/'after.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'adulterado'):self.verificar()

    def test_paths_symlinks_scan_version_and_coordinate_errors(self):
        self.publish(self.scan(2),self.scan(1))
        self.manifest['scan_depois']['arquivo']='../outside.json';save(self.path,self.manifest)
        with self.assertRaises(ValueError):self.verificar()
        self.publish(self.scan(2),self.scan(1));outside=self.root/'outside.json';outside.write_bytes((self.evidence/'after.json').read_bytes());(self.evidence/'after.json').unlink();(self.evidence/'after.json').symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'Symlink'):self.verificar()
        (self.evidence/'after.json').unlink()
        invalid=[self.scan(1,path='/outside.ts'),dict(self.scan(1),version='9'),self.scan(1)]
        invalid[-1]['results'][0]['start']['line']=0
        for data in invalid:
            self.publish(self.scan(2),data)
            with self.assertRaises(ValueError):self.verificar()

    def test_not_accepted_or_dry_run_not_valid_joint_evidence(self):
        self.publish(self.scan(2),self.scan(1));self.ent.linhas[0]['R']=0
        with self.assertRaisesRegex(ValueError,'aceite'):calcular_rris(self.path,self.ent,'criterio')
        self.ent.linhas[0]['R']=1;self.ent.contrato['modo']='dry-run'
        with self.assertRaisesRegex(ValueError,'real'):calcular_rris(self.path,self.ent,'criterio')


class RegressionTests(unittest.TestCase):
    def test_historical_public_functions_match_archived(self):
        for ex in ('E01','E02'):
            ls=[legacy.normalizar(l) for l in legacy.carregar(ex)]
            for l in ls:l['estrategia_curta']=l['tentativa_id'].split('_')[3]
            design=[l for l in ls if l['condicao']=='desenho'];order=sorted({l['estrategia_curta'] for l in design})
            old=json.loads((ROOT/f'outputs/resultados_consolidados/{ex}_metricas.json').read_text())
            for d in legacy.DEFS:
                self.assertEqual(legacy.indices(legacy.cadeia(design,d,order),d),old['definicoes'][d]['geral_por_tentativa'])
            self.assertEqual({k:legacy.custos(ls)[k] for k in old['custo']},old['custo'])
            self.assertEqual(legacy.custos(ls)['simuladas'],0)




class SanitizacaoSnapshotTests(unittest.TestCase):
    def test_snapshot_historico_e_adulteracao(self):
        from pipeline.etapas.e01_analise_sast.perfil import carregar as perfil, digest_regras
        source = ROOT/'outputs/feature04/preparacao/perfil_sast'
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/'perfil'
            shutil.copytree(source, dest)
            loaded = perfil(dest/'perfil.json')
            loaded.conferir()
            rules = dest/'regras_remotas.yaml'
            self.assertEqual(digest_regras(rules), loaded.dados['configs'][0]['sha256'])
            self.assertNotEqual(digest(rules), digest_regras(rules))
            rules.write_bytes(rules.read_bytes() + b'\n')
            with self.assertRaises(ValueError):
                loaded.conferir()

    def test_sidecar_nao_pode_redefinir_transformacao(self):
        from pipeline.etapas.e01_analise_sast.perfil import digest_regras
        source = ROOT/'outputs/feature04/preparacao/perfil_sast'
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)/'perfil'
            shutil.copytree(source, dest)
            sidecar = dest/'regras_remotas.yaml.sanitizacao.json'
            data = json.loads(sidecar.read_text())
            data['substituicao']['ocorrencias'] = 2
            sidecar.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                digest_regras(dest/'regras_remotas.yaml')

if __name__=='__main__':unittest.main()
