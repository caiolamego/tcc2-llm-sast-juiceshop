"""Cobertura v2 com Git, runners e ambiente simulados; sem serviços do alvo."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
import yaml
from pipeline.validation import coverage as c,coverage_runner as run
from pipeline.validation.coverage_audit import publicar,auditar
from pipeline.validation.identity import digest
from pipeline.validation.runner import ResultadoTier,ConfigValidacao,validar
from pipeline.validation.policy import opcoes
from pipeline.validation.conjunto_d import classificar
from pipeline.metrics.exporter import json_bytes
from pipeline.metrics.loader import _validar_contrato


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.wt=self.root/'target';self.wt.mkdir()
        self.patches=[patch.object(c,'RAIZ_REPO',self.root),patch.object(run,'RAIZ_REPO',self.root)]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.file='test/server/a.unit.test.ts';self.test=self.wt/self.file;self.test.parent.mkdir(parents=True);self.test.write_text('test works')
        (self.wt/'a.ts').write_text('const a = 1')
        self.d=self.root/'d.json';self.d.write_bytes(json_bytes({'schema_versao':'2.0','d':[]}))
        self.data={'schema_versao':'1.0','commit_alvo':'commit','hashes_catalogo':{},
          'conjunto_d':{'arquivo':'d.json','sha256':digest(self.d)},
          'grupos':{'g':{'dominio':'servidor','compilacoes':['servidor'],'comportamentos':['works'],
            'testes':[{'origem':'alvo','arquivo':self.file,'sha256':digest(self.test)}],
            'obrigatorios':[{'arquivo':self.file,'nome':'works'}]}},
          'casos':[{'caso_id':'AMP1','arquivo':'a.ts','check_id':'r','funcionalidade':'works','revisao':'adequada',
                    'grupos':['g'],'justificativa':'assertion inspected','evidencia_codigo':{'linha_inicio':1},
                    'lacunas':[],'testes_adicionais':[]}]}
        self.rev=self.root/'revisao.yaml';self.mapa=self.root/'mapa.yaml';self.write()
        self.base=self.root/'baseline.json'
        self.group_result={'grupo':'g','dominio':'servidor','testes':[{'id':self.file+' :: suite > works','arquivo':self.file,'nome':'suite > works','estado':'passou'}],
          'executados':[self.file+' :: suite > works'],'falhos':[],'falhos_novos':[],'intermitentes':[],
          'obrigatorios_aprovados':[self.file+' :: suite > works'],'comparavel':True,'falha_operacional':None,
          'reexecucoes':0,'espera_api_s':0,'duracao_s':0.1,'resultado':vars(ResultadoTier('T2',[],True,0.1))}
        self.save_base()
        self.env_patch=patch.object(c,'ambiente',return_value={'node':'fixture','porta_api':3101});self.env_patch.start();self.addCleanup(self.env_patch.stop)

    def write(self):
        self.rev.write_text(yaml.safe_dump(self.data));self.mapa.write_text(yaml.safe_dump(c.derivar_mapa(self.data,digest(self.rev))))

    def save_base(self):
        self.base.write_bytes(json_bytes({'schema_versao':'2.0','status':'concluido','commit_alvo':'commit',
           'cobertura':c.identidade(self.data,self.rev,self.mapa),'ambiente':{'node':'fixture'},
           'grupos':{'g':self.group_result},'compilacoes':{'servidor':{'passou':True}},'artefatos_sha256':{}}))

    def cfg(self):return ConfigValidacao(politica='relacionada_v2',cobertura=self.rev,mapa=self.mapa,arquivo_linha_de_base=self.base)

    def test_load_union_unknown_and_shared_file_gap(self):
        cat=SimpleNamespace(commit='commit',hashes={},casos=[{'caso_id':'AMP1','arquivo':'a.ts','check_id':'r'}])
        data=c.carregar(self.rev,self.mapa,self.wt,cat)
        self.assertTrue(c.selecionar(data,['a.ts','a.ts'],self.wt)['suficiente'])
        self.assertFalse(c.selecionar(data,['other.ts'],self.wt)['suficiente'])
        data['casos'].append(dict(data['casos'][0],caso_id='AMP2',revisao='insuficiente',justificativa='missing error assertion'))
        self.assertFalse(c.selecionar(data,['a.ts'],self.wt)['suficiente'])

    def test_invalid_map_duplicate_yaml_unknown_case_and_domain(self):
        self.mapa.write_text('schema_versao: "2.0"\nschema_versao: "2.0"\n')
        with self.assertRaises(ValueError):c.carregar(self.rev,self.mapa,self.wt)
        self.write();self.rev.write_text(self.rev.read_text()+'# changed')
        with self.assertRaises(ValueError):c.carregar(self.rev,self.mapa,self.wt)
        for mutate in ('dominio','compilacoes'):
            old=copy.deepcopy(self.data);self.data['grupos']['g'][mutate]='invalid';self.write()
            with self.assertRaises(ValueError):c.carregar(self.rev,self.mapa,self.wt)
            self.data=old
        self.write();self.data['casos'].append(self.data['casos'][0]);self.write()
        with self.assertRaises(ValueError):c.carregar(self.rev,self.mapa,self.wt)

    def test_test_hash_change_marks_coverage_insufficient(self):
        self.test.write_text('removed assertion')
        self.assertIn('avaliador alterado',c.selecionar(self.data,['a.ts'],self.wt)['motivos'][0])

    def test_same_test_in_two_groups_requires_shared_group(self):
        self.data['grupos']['g2']=copy.deepcopy(self.data['grupos']['g']);self.write()
        with self.assertRaisesRegex(ValueError,'grupo compartilhado'):c.carregar(self.rev,self.mapa,self.wt)

    def test_escape_and_external_symlink(self):
        outside=self.root/'outside';outside.write_text('data');(self.wt/'link').symlink_to(outside)
        for name in ('../outside','link','/etc/passwd'):
            with self.subTest(name=name),self.assertRaises(ValueError):c.interno(self.wt,name)

    def test_baseline_identity_status_artifacts_and_environment(self):
        sel=c.selecionar(self.data,['a.ts'],self.wt)
        c.validar_baseline(self.base,self.data,self.rev,self.mapa,self.wt,sel)
        original=self.base.read_bytes()
        for key,value in [('status','parcial'),('commit_alvo','wrong'),('ambiente',{'node':'other'}),('artefatos_sha256',{'missing.xml':'a'*64})]:
            b=json.loads(original);b[key]=value;self.base.write_bytes(json_bytes(b))
            with self.subTest(key=key),self.assertRaises((ValueError,OSError)):c.validar_baseline(self.base,self.data,self.rev,self.mapa,self.wt,sel)
        self.base.write_bytes(original)

    def test_junit_frontend_node_skip_error_missing_and_duplicates(self):
        xml=self.root/'r.xml';g=self.data['grupos']['g']
        xml.write_text(f'<testsuites><testsuite name="suite"><testcase file="{self.test}" name="works"/></testsuite></testsuites>')
        records=run.relatorio(xml,self.wt,g);self.assertEqual(records[0]['id'],self.file+' :: suite > works')
        xml.write_text('<testsuites><testsuite name="src/app/a.spec.ts"><testcase classname="src/app/a.spec.ts" name="suite &gt; works"/></testsuite></testsuites>')
        fg=dict(g,dominio='frontend',testes=[{'origem':'alvo','arquivo':'frontend/src/app/a.spec.ts'}])
        records=run.relatorio(xml,self.wt,fg);self.assertEqual(records[0]['arquivo'],'frontend/src/app/a.spec.ts')
        xml.write_text('<testsuites/>')
        with self.assertRaises(ValueError):run.relatorio(xml,self.wt,g)
        xml.write_text('<broken')
        with self.assertRaises(ValueError):run.relatorio(xml,self.wt,g)
        self.assertTrue(run.obrigatorios(g,[])[1])

    def test_staging_exclusive_and_cleanup_after_cancel(self):
        p=self.root/'tests/functional/juice_shop/g.unit.test.ts';p.parent.mkdir(parents=True);p.write_text('evaluation')
        g={'testes':[{'origem':'avaliacao','arquivo':p.relative_to(self.root).as_posix(),'destino':'test/server/temp/g.unit.test.ts','sha256':digest(p)}]}
        with self.assertRaises(KeyboardInterrupt):
            with run.staging(self.wt,g):
                self.assertTrue((self.wt/'test/server/temp/g.unit.test.ts').exists());raise KeyboardInterrupt
        self.assertFalse((self.wt/'test/server/temp').exists())
        dest=self.wt/'test/server/temp/g.unit.test.ts';dest.parent.mkdir();dest.write_text('unknown')
        with self.assertRaises(FileExistsError):
            with run.staging(self.wt,g):pass
        self.assertEqual(dest.read_text(),'unknown')

    def test_f_positive_and_independent_sast_without_wide_suites(self):
        callback=Mock()
        with patch.object(run,'compilar',return_value=ResultadoTier('T0',[],True,0.1)),patch.object(run,'executar_grupo',return_value=self.group_result),patch('pipeline.validation.runner.rodar_suite',side_effect=AssertionError('ampla')):
            result=validar(self.wt,['a.ts'],self.cfg(),callback)
        self.assertTrue(result.F_criterio);callback.assert_called_once()
        self.assertIn('cobertura_detalhada',result.to_dict())
        self.assertTrue(result.cobertura_detalhada['suficiente'])
        self.assertEqual(result.cobertura_detalhada['grupos_selecionados'],['g'])
        self.assertEqual(result.cobertura_detalhada['compilacoes'][0]['dominio'],'servidor')

    def test_unknown_file_and_modified_evaluator_prevent_f_positive(self):
        for files in (['a.ts','unknown.ts'],['unknown.ts']):
            callback=Mock()
            with patch.object(run,'compilar',return_value=ResultadoTier('T0',[],True,0.1)),patch.object(run,'executar_grupo',return_value=self.group_result):
                result=validar(self.wt,files,self.cfg(),callback)
            self.assertIsNone(result.F_criterio);callback.assert_called_once()

    def test_operational_uncertainty_and_measured_failure(self):
        for operational,failures,expected in [('timeout',[],None),(None,[self.file+' :: suite > works'],False)]:
            g=dict(self.group_result,falha_operacional=operational,falhos_novos=failures)
            callback=Mock()
            with patch.object(run,'compilar',return_value=ResultadoTier('T0',[],True,0.1)),patch.object(run,'executar_grupo',return_value=g):
                r=validar(self.wt,['a.ts'],self.cfg(),callback)
            self.assertEqual(r.F_criterio,expected);callback.assert_called_once()

    def test_new_d_preserves_definitions_and_does_not_pollute_legacy(self):
        entry={'arquivo':self.file,'nome':'works','criterio':'c'}
        self.d.write_bytes(json_bytes({'schema_versao':'2.0','d':[entry]}))
        ident=self.file+' :: suite > works'
        self.assertEqual(classificar([ident],self.d)['d_criterio'],[ident])
        self.assertEqual(classificar([ident])['d_criterio'],[])
        self.assertEqual(classificar([ident],self.d)['d_marcador'],[])

    def test_three_f_definitions_use_the_explicit_versioned_d(self):
        ident=self.file+' :: suite > works'
        self.d.write_bytes(json_bytes({'schema_versao':'2.0','d':[{'arquivo':self.file,'nome':'works','criterio':'c'}]}))
        self.data['conjunto_d']['sha256']=digest(self.d);self.write();self.save_base()
        g=dict(self.group_result,falhos_novos=[ident])
        with patch.object(run,'compilar',return_value=ResultadoTier('T0',[],True,0.1)),patch.object(run,'executar_grupo',return_value=g):
            result=validar(self.wt,['a.ts'],self.cfg())
        self.assertEqual((result.F_sem_separacao,result.F_marcador,result.F_criterio),(False,False,True))

    def test_publication_lock_corruption_existing_and_write_failure(self):
        out=self.root/'report';source=self.root/'input';source.write_text('source');inputs={source:digest(source)}
        publicar(out,{'r.json':b'{}\n'},inputs)
        with self.assertRaises(ValueError):publicar(out,{},inputs)
        out2=self.root/'next';lock=out2.with_name(out2.name+'.lock');lock.write_text('other')
        with self.assertRaises(ValueError):publicar(out2,{},inputs)
        self.assertEqual(lock.read_text(),'other');lock.unlink()
        with patch.object(Path,'write_bytes',side_effect=OSError('write failure')),self.assertRaises(OSError):publicar(out2,{'r':b''},inputs)
        self.assertFalse(lock.exists());self.assertFalse(out2.exists())
        source.write_text('changed')
        with self.assertRaises(ValueError):publicar(out2,{},inputs)

    def test_policy_requires_review_and_old_policies_unchanged(self):
        with self.assertRaises(ValueError):opcoes(SimpleNamespace(politica_validacao='relacionada_v2',mapa_testes=self.mapa))
        old=opcoes(SimpleNamespace());self.assertNotIn('cobertura_funcional',old)
        new=opcoes(SimpleNamespace(politica_validacao='relacionada_v2',mapa_testes=self.mapa,cobertura_funcional=self.rev))
        self.assertEqual(new['cobertura_funcional'],self.rev)

    def test_cli_help_outside_repo(self):
        for file in ('scripts/audit/audit_functional_coverage.py','scripts/experiment/validate_functional_coverage.py'):
            r=subprocess.run([sys.executable,str(ROOT/file),'--help'],cwd=self.root,text=True,capture_output=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stderr)

    def test_auditor_is_read_only_deterministic_and_reconciles_actual_evidence(self):
        catalog=self.root/'catalogo.json';catalog.write_text('[]')
        for name in ('catalogo_meta.json','exclusoes.json'):(self.root/name).write_text('{}')
        cat=SimpleNamespace(ampliado=True,commit='commit',hashes={},casos=self.data['casos'],
                            meta={'arquivos_fonte':{'a.ts':digest(self.wt/'a.ts')}})
        with patch('pipeline.validation.coverage_audit.carregar_catalogo',return_value=cat),\
             patch('pipeline.validation.coverage_audit.RAIZ_REPO',self.root),\
             patch('pipeline.validation.coverage_audit.subprocess.check_output',side_effect=['commit\n','']*2),\
             patch('pipeline.validation.runner._rodar',side_effect=AssertionError('auditor executou teste')):
            a,inputs,summary=auditar(catalog,self.wt,self.mapa,self.rev,self.base)
            b,_,_=auditar(catalog,self.wt,self.mapa,self.rev,self.base)
        self.assertEqual(a,b);self.assertEqual(summary['preparados'],1)
        publicar(self.root/'audit1',a,inputs);publicar(self.root/'audit2',b,inputs)
        self.assertEqual((self.root/'audit1/cobertura_por_caso.csv').read_bytes(),(self.root/'audit2/cobertura_por_caso.csv').read_bytes())

    def test_contract_v4_is_opt_in_and_requires_matching_hashes(self):
        entry=SimpleNamespace(execucao='TEST',catalogo=SimpleNamespace(commit='c',hashes={},casos=[{'caso_id':'AMP1'}]))
        entry.contrato={'schema_versao':'4.0','execucao':'TEST','modo':'preflight','commit_alvo':'c','hashes_catalogo':{},
          'casos':['AMP1'],'estrategias':['P1'],'diagnosticos':[],'comparador':'ocorrencias_contexto_v2','baseline_testes_sha256':'d'*64,
          'validacao':{'politica_validacao':'relacionada_v2','cache_validacao':'desligado','repeticao_api':'ampla',
             'implementacao':{'runner.py':'a'*64},'ambientes':[],'mapa_testes_sha256':'b'*64,'baseline_sha256':'d'*64,
             'cobertura':{'mapa_sha256':'b'*64,'revisao_sha256':'c'*64,'conjunto_d_sha256':'e'*64}}}
        with patch('pipeline.metrics.loader._perfil'),patch('pipeline.metrics.loader._cobertura'):
            _validar_contrato(entry)
            entry.contrato['schema_versao']='3.0'
            with self.assertRaises(ValueError):_validar_contrato(entry)
            entry.contrato['schema_versao']='4.0';entry.contrato['validacao']['cobertura']['mapa_sha256']='f'*64
            with self.assertRaises(ValueError):_validar_contrato(entry)

    def test_portable_snapshot_detects_tampering(self):
        from pipeline.execucao_ampliada import snapshot_cobertura
        from pipeline.metrics.loader import _cobertura
        from pipeline.metrics.loader import Entrada
        out=self.root/'run';out.mkdir()
        args=SimpleNamespace(cobertura_funcional=self.rev,mapa_testes=self.mapa,baseline_testes=self.base)
        contract={'baseline_testes_sha256':digest(self.base),'validacao':{'cobertura':c.identidade(self.data,self.rev,self.mapa)}}
        with patch('pipeline.execucao_ampliada.RAIZ_REPO',self.root):snapshot_cobertura(args,out,self.data,contract)
        entry=Entrada(out,'TEST',None,contract,[],[],None)
        _cobertura(entry)
        (out/'cobertura_funcional/revisao.yaml').write_text('tampered')
        with self.assertRaises(ValueError):_cobertura(entry)

    def test_angular_command_is_selective_and_has_junit(self):
        group=copy.deepcopy(self.data['grupos']['g']);group['dominio']='frontend'
        group['testes']=[{'origem':'alvo','arquivo':'frontend/src/app/a.spec.ts'}]
        group['obrigatorios']=[{'arquivo':'frontend/src/app/a.spec.ts','nome':'works'}]
        def execute(tier,cmd,cwd,timeout,env):
            self.assertIn('--include=src/app/a.spec.ts',cmd);self.assertIn('--watch=false',cmd)
            self.assertEqual(cwd,self.wt/'frontend');self.assertEqual(timeout,300)
            output=Path(next(x.split('=',1)[1] for x in cmd if x.startswith('--output-file=')))
            output.write_text('<testsuites><testsuite><testcase classname="src/app/a.spec.ts" name="suite &gt; works"/></testsuite></testsuites>')
            return ResultadoTier('T_FRONTEND',cmd,True,0.1,codigo_saida=0),0
        with patch('pipeline.validation.runner._rodar',side_effect=execute):
            r=run.executar_grupo(self.wt,'front',group,self.root/'angular')
        self.assertTrue(r['comparavel']);self.assertIn('primeira.xml',r['relatorios_junit'])

    def test_api_disabled_and_compiler_failure_do_not_call_broad_suites(self):
        self.data['grupos']['g']['dominio']='api'
        self.data['grupos']['g']['testes'][0]['arquivo']='test/api/a.test.ts'
        p=self.wt/'test/api/a.test.ts';p.parent.mkdir();p.write_text('api fixture')
        self.data['grupos']['g']['testes'][0]['sha256']=digest(p)
        self.data['grupos']['g']['obrigatorios'][0]['arquivo']='test/api/a.test.ts'
        self.write();self.save_base();cfg=self.cfg();cfg.rodar_t4=False
        with patch.object(run,'compilar',return_value=ResultadoTier('T0',[],True,0.1)),\
             patch.object(run,'executar_grupo',side_effect=AssertionError('API desabilitada')):
            result=validar(self.wt,['a.ts'],cfg)
        self.assertIsNone(result.F_criterio)
        callback=Mock()
        with patch.object(run,'compilar',return_value=ResultadoTier('T0',[],False,0.1,motivo='falha')):
            result=validar(self.wt,['a.ts'],cfg,callback)
        self.assertFalse(result.F_criterio);callback.assert_called_once()


if __name__=='__main__':unittest.main()
