"""Feature 03: fixtures locais, contratos e regressão textual; nenhuma consulta web."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import yaml

from pipeline.etapas.e03_contexto_rag import recuperacao as r
from pipeline.etapas.e04_prompt import montagem as b
from pipeline.orquestracao import preflight as amp
from pipeline.etapas.e02_catalogo.catalogo import carregar, digest


def fixture(base):
    base.mkdir(parents=True,exist_ok=True)
    index={'schema_versao':'1.0','base_versao':'1.0','fallback':'generico',
           'documentos':{c:c+'.md' for c in r.CATEGORIAS},
           'cwe':{'CWE-89':'injection','CWE-79':'cross_site_scripting','CWE-362':'concurrency'}}
    (base/'_index.yaml').write_text(yaml.safe_dump(index))
    for cat in r.CATEGORIAS:
        meta={'schema_versao':'1.0','categoria':cat,'status':'PRONTO','versao_documento':'1.0',
              'fontes':[{'titulo':'Fixture','url':'https://example.test/source','consultado_em':'2026-10-13'}]}
        body='\n'.join(f'## {i}. {h}\nTexto {cat}.' for i,h in enumerate(r.SECOES,1))+'\n```typescript\nbad();\n```\n```typescript\ngood();\n```\n'
        (base/(cat+'.md')).write_text('---\n'+yaml.safe_dump(meta)+'---\n'+body,encoding='utf-8')
    r.publicar_manifesto(base)
    return base


class BaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=fixture(Path(self.tmp.name)/'base')

    def test_cwe_order_category_fallback_and_historic(self):
        for case,cat,reason,cwe in [
            ({'cwe_ids':['CWE-000','CWE-362','CWE-79'],'categoria_rag':'injection'},'concurrency','cwe','CWE-362'),
            ({'cwe_ids':[],'categoria_rag':'injection'},'injection','categoria_catalogo',None),
            ({'cwe_ids':['CWE-000'],'categoria_rag':None},'generico','fallback',None),
            ({'cwe':['CWE-79: Cross Site Scripting']},'cross_site_scripting','cwe','CWE-79')]:
            before=copy.deepcopy(case);got=r.recuperar(case,self.base)
            self.assertEqual((got.categoria,got.motivo,got.cwe),(cat,reason,cwe))
            self.assertEqual(case,before)
            self.assertNotIn('fontes:',got.corpo)
            self.assertEqual(got.corpo_sha256,r.sha(got.corpo.encode()))

    def test_body_limit_and_bad_cwe_list(self):
        path=self.base/'injection.md';raw=path.read_text()
        header,body=raw.split('---\n',2)[1:]
        path.write_text('---\n'+header+'---\n'+body+'x'*(20000-len(body)))
        _,body2=r.ler_documento(path,'injection');self.assertEqual(len(body2),20000)
        path.write_text(path.read_text()+'x')
        with self.assertRaises(r.BaseInvalida):r.ler_documento(path,'injection')
        path.write_text(raw)
        for case in [{'cwe':42},{'cwe_ids':'CWE-89'}]:
            with self.assertRaises(r.BaseInvalida):r.recuperar(case,self.base)

    def test_audit_metadata_never_selects_document(self):
        case={'cwe_ids':['CWE-89'],'classificacao_auditoria':'falso_positivo','desafios':['irrelevante']}
        expected=r.recuperar(case,self.base)
        self.assertEqual(expected,r.recuperar({**case,'classificacao_auditoria':'confirmado'},self.base))

    def test_manifest_deterministic_and_exclusive(self):
        other=fixture(Path(self.tmp.name)/'other')
        self.assertEqual((self.base/'manifesto.json').read_bytes(),(other/'manifesto.json').read_bytes())
        old=(self.base/'manifesto.json').read_bytes()
        with self.assertRaises(FileExistsError):r.publicar_manifesto(self.base)
        self.assertEqual(old,(self.base/'manifesto.json').read_bytes())

    def test_index_corruption_duplicate_keys_and_types(self):
        path=self.base/'_index.yaml';raw=path.read_text()
        cases=[raw+'fallback: generico\n',raw.replace("'1.0'","'9.0'",1),
               raw.replace('injection.md','../injection.md'),raw.replace('injection.md','/tmp/injection.md'),
               raw.replace('injection.md','[invalid]'),raw.replace('CWE-89: injection','CWE-89: [invalid]')]
        for text in cases:
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaises(r.BaseInvalida):r.carregar_base(self.base)
        path.write_text(raw)

    def test_document_errors(self):
        path=self.base/'injection.md';raw=path.read_text()
        for text in ['',raw.replace('PRONTO','RASCUNHO'),raw.replace('categoria: injection','categoria: generico'),
                     raw.replace("'1.0'","'9.0'",1),raw.replace('https://example.test/source','http://example.test/source'),
                     raw.replace('2026-10-13','invalid'),raw.replace('fontes:', 'outras_fontes:'),
                     raw.replace('## 1. Descrição e sinais','## Ausente'),raw+'a'*20001,
                     raw.replace('status: PRONTO','status: PRONTO\nstatus: PRONTO')]:
            with self.subTest(text=text[:30]):
                path.write_text(text)
                with self.assertRaises(r.BaseInvalida):r.carregar_base(self.base)
        path.write_bytes(b'\xff')
        with self.assertRaises(r.BaseInvalida):r.carregar_base(self.base)

    def test_missing_document_and_external_symlink(self):
        path=self.base/'injection.md';raw=path.read_bytes();path.unlink()
        with self.assertRaises(r.BaseInvalida):r.carregar_base(self.base)
        outside=Path(self.tmp.name)/'outside.md';outside.write_bytes(raw);path.symlink_to(outside)
        with self.assertRaisesRegex(r.BaseInvalida,'fora da base'):r.carregar_base(self.base)

    def test_changes_not_hidden_by_cache(self):
        r.recuperar({'cwe_ids':['CWE-89']},self.base)
        path=self.base/'injection.md';path.write_text(path.read_text()+'Changed\n')
        with self.assertRaisesRegex(r.BaseInvalida,'Manifesto diverge'):r.recuperar({'cwe_ids':['CWE-89']},self.base)

    def test_manifest_tampered_and_missing(self):
        path=self.base/'manifesto.json';path.write_text('{}')
        with self.assertRaises(r.BaseInvalida):r.carregar_base(self.base)
        path.unlink()
        with self.assertRaises(r.BaseInvalida):r.carregar_base(self.base)

    def test_cli_readonly_from_other_directory(self):
        snapshot={p.name:p.read_bytes() for p in self.base.iterdir()}
        cmd=[sys.executable,str(ROOT/'scripts/experimento/validar_base_rag.py'),'--base',str(self.base)]
        result=subprocess.run(cmd,cwd=self.tmp.name,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(snapshot,{p.name:p.read_bytes() for p in self.base.iterdir()})
        self.assertEqual(subprocess.run(cmd+['--publicar-manifesto'],cwd=self.tmp.name,capture_output=True).returncode,1)
        self.assertEqual(subprocess.run(cmd[:2]+['--help'],cwd=self.tmp.name,capture_output=True).returncode,0)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.base=fixture(root/'base');self.wt=root/'wt';self.wt.mkdir()
        (self.wt/'a.ts').write_text('const x = input.value;\n')
        self.case={'arquivo':'a.ts','linha_inicio':1,'linha_fim':1,'check_id':'example.rule','cwe':['CWE-89: SQL'],
                   'cwe_ids':['CWE-89'],'mensagem':'Example','classificacao_auditoria':'SECRET_AUDIT_METADATA'}

    def test_order_context_and_only_guided_difference(self):
        with patch.object(b,'DIR_KB',self.base):
            p3=b.montar(self.case,self.wt,'P3');p4=b.montar(self.case,self.wt,'P4')
        text=p3.mensagens[1]['content'];body=r.recuperar(self.case,self.base).corpo
        elements=['Tarefa:', 'Arquivo:',b.bloco_alerta(self.case),'Contexto técnico recuperado para apoiar a análise:',body,b.RESTRICOES,b.FORMATO]
        positions=[text.index(t) for t in elements]
        self.assertEqual(positions,sorted(positions))
        self.assertEqual(p4.mensagens[1]['content'].replace('\n\n'+b.carregar_roteiro()[0],''),text)
        self.assertEqual(p3.metadados_rag(),p4.metadados_rag())
        self.assertNotIn('SECRET_AUDIT_METADATA',text)
        self.assertNotIn('fontes:',text)
        self.assertNotIn('status: PRONTO',text)
        self.assertTrue(p3.usa_rag)

    def test_nonrag_independent_and_rag_requires_base(self):
        with patch.object(b,'DIR_KB',Path(self.tmp.name)/'absent'):
            for e in ['P1','P2','P1L']:
                p=b.montar(self.case,self.wt,e)
                self.assertFalse(p.usa_rag)
                self.assertTrue(all(v is None for k,v in p.metadados_rag().items() if k!='usa_rag'))
            for e in ['P3','P4']:
                with self.assertRaises(b.EstrategiaIndisponivel):b.montar(self.case,self.wt,e)

    def test_regression_all_234_and_156_archived(self):
        cases=json.loads((ROOT/'outputs/catalogos/ampliado_v1/catalogo_issues.json').read_text())
        references=json.loads((ROOT/'outputs/feature03/preparacao/referencia_prompts_semrag.json').read_text())
        # Fixtures capturadas antes de alterar o builder; checkout não é restaurado por este teste.
        wt=ROOT/'workspace/catalogo-alvo'
        if not wt.exists():self.skipTest('Checkout oficial ausente; regressão local coberta nas fixtures')
        for case in cases:
            for e in ['P1','P2','P1L']:
                with self.subTest(case=case['caso_id'],e=e):
                    got=amp.projecao_prompt(b.montar(case,wt,e).to_dict())
                    self.assertEqual(got,references[f'{case["caso_id"]}_{e}'])
                    if e!='P1L':
                        old=json.loads((ROOT/f'outputs/feature02/AMP_PREFLIGHT_01/prompts/{case["caso_id"]}_{e}.json').read_text())
                        self.assertEqual(got,amp.projecao_prompt(old))


class ContratoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.base=fixture(self.root/'base');self.wt=self.root/'wt';self.wt.mkdir()
        (self.wt/'a.ts').write_text('let x=1;\n')
        self.case={'caso_id':'AMPfixture','arquivo':'a.ts','linha_inicio':1,'linha_fim':1,'cwe':[], 'mensagem':'x','check_id':'r'}
        self.catalog=SimpleNamespace(commit='a'*40,hashes={'catalogo':'x'})
        self.profile=SimpleNamespace(hash='profile',dados={'semgrep_versao':'1.177.0'})
        self.args=SimpleNamespace(execucao='TEST',somente_preflight=True,dry_run=False,baseline_testes=self.root/'absent',
                                  estrategias=['P1','P2'],diagnosticos=[])

    def current(self):
        with patch.object(b,'DIR_KB',self.base):return amp.contrato(self.args,self.catalog,self.profile,[self.case])

    def old(self):
        current=self.current();old=copy.deepcopy(current);old['schema_versao']='1.0';old.pop('componentes_prompt_sha256')
        old['prompts_validacao_sha256']['builder.py']='historical-hash'
        out=self.root/'out';(out/'prompts').mkdir(parents=True)
        for e in self.args.estrategias:
            p=b.montar(self.case,self.wt,e).to_dict()
            for k in list(p):
                if k.startswith('rag_'):p.pop(k)
            amp.salvar(out/'prompts'/f'AMPfixture_{e}.json',p)
        amp.salvar(out/'contrato_execucao.json',old)
        return old,current,out

    def test_v3_without_rag_does_not_depend_on_base(self):
        got=self.current();self.assertEqual(got['schema_versao'],'3.0');self.assertNotIn('rag',got)
        self.assertNotIn('builder.py',got['prompts_validacao_sha256'])
        shutil.rmtree(self.base)
        self.assertEqual(got,self.current())

    def test_v2_rag_tracks_full_base_and_versions(self):
        self.args.estrategias=['P3','P4'];old=self.current()
        self.assertEqual(len(old['rag']['documentos']),10)
        path=self.base/'injection.md';path.write_text(path.read_text()+'Changed\n')
        with self.assertRaises(r.BaseInvalida):self.current()
        (self.base/'manifesto.json').unlink();r.publicar_manifesto(self.base)
        self.assertNotEqual(old,self.current())

    def test_old_complete_equivalence_readonly(self):
        old,current,out=self.old();snapshot={p:p.read_bytes() for p in out.rglob('*') if p.is_file()}
        amp.validar_compatibilidade_antiga(old,current,out,[self.case],self.wt)
        self.assertEqual(snapshot,{p:p.read_bytes() for p in out.rglob('*') if p.is_file()})

    def test_old_incomplete_or_changed_evidence_rejected(self):
        old,current,out=self.old();path=out/'prompts/AMPfixture_P2.json';raw=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(ValueError,'evidência'):amp.validar_compatibilidade_antiga(old,current,out,[self.case],self.wt)
        data=json.loads(raw);data['mensagens'][0]['content']='changed';amp.salvar(path,data)
        with self.assertRaisesRegex(ValueError,'mensagens'):amp.validar_compatibilidade_antiga(old,current,out,[self.case],self.wt)

    def test_old_scientific_fields_guide_and_rag_rejected(self):
        old,current,out=self.old()
        for changed in [dict(current,commit_alvo='b'*40),dict(current,estrategias=['P3']),
                        dict(current,prompts_validacao_sha256={'runner.py':'changed'})]:
            with self.assertRaisesRegex(ValueError,'Contrato incompatível'):
                amp.validar_compatibilidade_antiga(old,changed,out,[self.case],self.wt)

    def test_before_attempt_revalidates_even_for_p1_in_rag_execution(self):
        self.args.estrategias=['P1','P3'];current=self.current()
        prep=SimpleNamespace(componentes_prompt=current['componentes_prompt_sha256'],rag_base_sha256=current['rag']['manifesto_sha256'])
        with patch.object(b,'DIR_KB',self.base):
            p=b.montar(self.case,self.wt,'P1');amp.conferir_prompt_contrato(prep,p,self.args.estrategias)
            path=self.base/'injection.md';path.write_text(path.read_text()+'changed')
            with self.assertRaises(ValueError):amp.conferir_prompt_contrato(prep,p,self.args.estrategias)

    def test_full_preflight_cli_never_creates_client_applies_or_validates(self):
        from pipeline.orquestracao import campanha as rp
        from pipeline.etapas.e02_catalogo.catalogo import Catalogo
        from pipeline.etapas.e01_analise_sast.semgrep import Finding, ScanResultado
        wt=self.root/'workspace/wt-1';wt.mkdir(parents=True);(wt/'a.ts').write_text('let x=1;\n')
        runner=self.root/'src/pipeline/etapas/e07_validacao/camadas.py';runner.parent.mkdir(parents=True);runner.write_text('#fixture')
        case={**self.case,'coluna_inicio':1,'coluna_fim':2,'elegivel':True}
        catalog=Catalogo(self.root/'catalog.json',[case],'ampliado','a'*40,{'catalogo':'x'},
                        {'semgrep_versao':'1.177.0','arquivos_fonte':{'a.ts':digest(wt/'a.ts')}})
        profile=SimpleNamespace(hash='profile',dados={'semgrep_versao':'1.177.0','id_regras':['r']},no_escopo=lambda _:True)
        result=ScanResultado([Finding('r','a.ts',1,1,'INFO','x',(),(),'security','','',start_col=1,end_col=2)],[],'1.177.0')
        def scanner(wt,profile,path,exe):
            amp.salvar(path,{'results':[]})
            return result
        argv=['pipeline','--execucao','TEST','--catalogo',str(catalog.caminho),'--perfil-sast','fake',
              '--saida',str(self.root/'out'),'--estrategias','P1,P2,P3,P4','--somente-preflight','--k','1']
        with patch.object(sys,'argv',argv),patch.object(amp,'RAIZ_REPO',self.root),patch.object(b,'DIR_KB',self.base),\
             patch('pipeline.etapas.e02_catalogo.catalogo.carregar',return_value=catalog),patch.object(amp,'head',return_value='a'*40),\
             patch.object(amp,'limpo',return_value=True),patch.object(amp,'carregar_perfil',return_value=profile),\
             patch.object(amp,'conferir_versao'),patch.object(amp,'scan_perfil',side_effect=scanner),\
             patch.object(amp,'carregar_scan_perfil',return_value=result),\
             patch('pipeline.etapas.e05_geracao_llm.cliente_openai.ConfigLLM.do_env',side_effect=AssertionError('LLM proibida')),\
             patch.object(rp,'aplicar',side_effect=AssertionError('Patch proibido')),\
             patch.object(rp,'validar',side_effect=AssertionError('Testes funcionais proibidos')),\
             patch.object(rp.PoolWorktrees,'restaurar',side_effect=AssertionError('Restauração proibida')):
            rp.main()
            self.assertEqual((wt/'a.ts').read_text(),'let x=1;\n')
            self.assertFalse((wt/'node_modules').exists())
            out=self.root/'out';report=json.loads((out/'preflight.json').read_text())
            self.assertEqual(len(report['prompts']),4)
            self.assertEqual(sum(p['usa_rag'] for p in report['prompts']),2)
            snapshot={p:p.read_bytes() for p in out.rglob('*') if p.is_file()}
            rp.main()  # Contrato 2.0 retomado sem reescrever artefatos.
            self.assertEqual(snapshot,{p:p.read_bytes() for p in out.rglob('*') if p.is_file()})
            path=self.base/'generico.md';path.write_text(path.read_text()+'changed')
            with self.assertRaises(SystemExit):rp.main()

    def test_official_old_contract_copies_equivalent_and_hash_unchanged(self):
        source=ROOT/'outputs/feature02/AMP_PREFLIGHT_01'
        out=self.root/'official';shutil.copytree(source,out)
        old=json.loads((out/'contrato_execucao.json').read_text())
        current=copy.deepcopy(old);current['schema_versao']='2.0';current['prompts_validacao_sha256'].pop('builder.py')
        current['componentes_prompt_sha256']=b.componentes_contrato(['P1','P2'])
        cases=json.loads((ROOT/'outputs/catalogos/ampliado_v1/catalogo_issues.json').read_text())
        wt=ROOT/'workspace/catalogo-alvo'
        if not wt.exists():self.skipTest('Checkout oficial ausente')
        snapshot={p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.is_file()}
        amp.validar_compatibilidade_antiga(old,current,out,cases,wt)
        self.assertEqual(snapshot,{p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.is_file()})


if __name__=='__main__':unittest.main()
