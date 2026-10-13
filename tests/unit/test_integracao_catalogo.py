"""Integração AMP: identidade, cobertura, contratos e isolamento sem API/rede."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import copy
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.catalogo import carregar, Catalogo, digest
from pipeline.sast.perfil import carregar as carregar_perfil
from pipeline.sast.semgrep_client import Finding, ScanResultado
from pipeline.sast.comparacao import comparar, gate, chave
from pipeline import execucao_ampliada as amp
from pipeline.llm.falso import resposta_falsa_ampliada
from pipeline.run_pipeline import nome_tentativa, _aceita_estrita
from scripts.audit.build_sast_profile import construir

ROOT=Path(__file__).resolve().parents[2]


def finding(line=1,path='a.ts',rule='tcc.example',col=1):
    return Finding(rule,path,line,line,'INFO','msg',(),(),'security','','',start_col=col,end_col=col+1)


def scan(fs, errors=None, fail=None):
    return ScanResultado(fs,errors or [],'1.177.0',fail)


class ComparacaoTests(unittest.TestCase):
    def test_unchanged_and_shift(self):
        f=finding(2)
        s=scan([f])
        self.assertEqual(comparar(s,s,chave(f),{})['R'],0)
        result=comparar(s,scan([finding(3)]),chave(f),{'a.ts':(b'head\nx\ntail\n',b'new\nhead\nx\ntail\n')})
        self.assertEqual((result['R'],result['M']),(0,1))

    def test_remove_one_of_two(self):
        a,b=finding(1),finding(3)
        sources={'a.ts':(b'bad\nmarker\nother\ntail\n',b'marker\nother\ntail\n')}
        after=scan([finding(2)])
        result=comparar(scan([a,b]),after,chave(a),sources)
        self.assertEqual((result['R'],result['M']),(1,1))
        self.assertEqual(comparar(scan([a,b]),after,chave(b),sources)['R'],0)

    def test_second_occurrence_is_new(self):
        a=finding(1)
        result=comparar(scan([a]),scan([a,finding(3)]),chave(a),{'a.ts':(b'x\nend\n',b'x\nend\nx\n')})
        self.assertEqual(result['M'],0)
        self.assertEqual(result['novas_issues_qtd'],1)

    def test_same_count_different_rules(self):
        a=finding()
        result=comparar(scan([a]),scan([finding(rule='tcc.new')]),chave(a),{'a.ts':(b'x\n',b'y\n')})
        self.assertEqual((result['R'],result['M']),(1,0))

    def test_modified_same_rule_is_indeterminate(self):
        a=finding()
        result=comparar(scan([a]),scan([a]),chave(a),{'a.ts':(b'x\n',b'y\n')})
        self.assertEqual((result['R'],result['M']),(None,None))
        self.assertEqual(result['possiveis_novas_issues_qtd'],1)

    def test_repeated_blocks_are_not_guessed(self):
        a=finding(1)
        result=comparar(scan([a,finding(3)]),scan([finding(1)]),chave(a),{'a.ts':(b'x\nblank\nx\nblank\n',b'x\nblank\n')})
        self.assertIsNone(result['R'])
        self.assertTrue(result['ambiguos'])

    def test_existing_parsing_in_unchanged_file_is_limited(self):
        a=finding()
        error={'path':'other.ts','type':'Syntax error','message':'problem'}
        result=comparar(scan([a],[error]),scan([a],[error]),chave(a),{})
        self.assertEqual(result['M'],1)
        self.assertEqual(result['cobertura_limitada'],[error])

    def test_new_parsing_changed_file_and_timeout(self):
        a=finding()
        for before,after,sources in ((scan([a]),scan([], [{'path':'a.ts','type':'Syntax'}]),{}),
           (scan([a],[{'path':'a.ts','type':'Syntax'}]),scan([]),{'a.ts':(b'x\n',b'y\n')}),
           (scan([a]),scan([],fail='timeout'),{})):
            with self.subTest(before=before,after=after):
                r=comparar(before,after,chave(a),sources)
                self.assertIsNone(r['R']);self.assertIsNone(r['M'])

    def test_global_new_finding_in_other_file(self):
        a=finding()
        result=comparar(scan([a]),scan([a,finding(path='other.ts')]),chave(a),{})
        self.assertEqual(result['M'],0)


class CatalogoPerfilTests(unittest.TestCase):
    def test_historical_and_expanded(self):
        historic=carregar(ROOT/'outputs/sast_antes/catalogo_issues.json')
        expanded=carregar(ROOT/'outputs/catalogos/ampliado_v1/catalogo_issues.json')
        self.assertFalse(historic.ampliado);self.assertEqual(len(historic.casos),12)
        self.assertTrue(expanded.ampliado);self.assertEqual(len(expanded.casos),78)
        self.assertEqual(sum(c['classificacao_auditoria']=='falso_positivo' for c in expanded.casos),21)
        self.assertTrue(any(c['severidade']=='INFO' for c in expanded.casos))
        self.assertTrue(any(c['owasp_2025'] is None for c in expanded.casos))

    def test_altered_catalog_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            for p in (ROOT/'outputs/catalogos/ampliado_v1').glob('*.json'):(d/p.name).write_bytes(p.read_bytes())
            p=d/'catalogo_issues.json';data=json.loads(p.read_text());data[0]['caso_id']='BAD';p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'Hash'):carregar(p)

    def test_profile_builder_hashes_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);rules=p/'rules';rules.mkdir();remote=p/'remote.yaml';local=rules/'local.yaml';excluded=p/'ignore'
            remote.write_text('rules:\n- id: r.remote\n  languages: [javascript]\n  pattern: x\n  message: x\n  severity: INFO\n')
            local.write_text(remote.read_text().replace('r.remote','tcc.local'))
            excluded.write_text('test/\n')
            artifacts=construir(remote,rules,excluded);out=p/'profile';out.mkdir()
            for name,data in artifacts.items():(out/name).write_bytes(data)
            profile=carregar_perfil(out/'perfil.json')
            self.assertFalse(profile.no_escopo('frontend/.npmrc'))
            self.assertTrue(profile.no_escopo('a.ts'))
            (out/'regras_locais.yaml').write_text('changed')
            with self.assertRaises(ValueError):profile.conferir()
            local.write_text(remote.read_text())
            with self.assertRaisesRegex(ValueError,'duplicados'):construir(remote,rules,excluded)

    def test_gate_exact_multiset(self):
        c=SimpleNamespace(casos=[{'check_id':'tcc.example','arquivo':'a.ts','linha_inicio':1,'linha_fim':1,'coluna_inicio':1,'coluna_fim':2}])
        self.assertTrue(gate(c,scan([finding()]))['reproduzido'])
        self.assertFalse(gate(c,scan([]))['reproduzido'])
        self.assertFalse(gate(c,scan([finding(),finding(2)]))['reproduzido'])
        self.assertFalse(gate(c,scan([finding()],fail='timeout'))['reproduzido'])

    def test_semowasp_and_indeterminate_chain(self):
        tid=nome_tentativa({'caso_id':'AMP123','owasp_2025':None,'sigla_vuln':'OUTRO'},'P1','TEST')
        self.assertEqual(tid,'AMP123_SEMOWASP_OUTRO_P1_TEST')
        self.assertFalse(_aceita_estrita({'classificacao_final':'indeterminada_sast'}))

    def test_dry_run_safe_and_unsupported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'a.ts').write_text('let x=1\nlet x2=2\n')
            issue={'arquivo':'a.ts','linha_inicio':2,'linha_fim':2}
            data=json.loads(resposta_falsa_ampliada(issue,p))
            self.assertEqual((p/'a.ts').read_text().count(data['edicoes'][0]['trecho_original']),1)
            self.assertTrue(data['edicoes'][0]['trecho_corrigido'].startswith('// dry-run'))
            self.assertIsNone(resposta_falsa_ampliada({**issue,'arquivo':'a.html'},p))


class PreflightTests(unittest.TestCase):
    def test_preflight_without_dependencies_and_contract_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);wt=r/'workspace/wt-1';wt.mkdir(parents=True);(wt/'a.ts').write_text('let a=1\n')
            runner=r/'src/pipeline/validation/runner.py';runner.parent.mkdir(parents=True);runner.write_text('#fixture')
            case={'caso_id':'AMPtest','check_id':'tcc.example','arquivo':'a.ts','linha_inicio':1,'linha_fim':1,
                  'coluna_inicio':1,'coluna_fim':2,'mensagem':'x','cwe':[]}
            catalog=Catalogo(r/'catalogo.json',[case],'ampliado','a'*40,{'catalogo':'hash'},
                {'semgrep_versao':'1.177.0','arquivos_fonte':{'a.ts':digest(wt/'a.ts')}})
            profile=SimpleNamespace(hash='profile',dados={'semgrep_versao':'1.177.0','id_regras':['tcc.example']},no_escopo=lambda p:True)
            args=SimpleNamespace(perfil_sast=r/'perfil.json',saida=r/'saida',execucao='PREFLIGHT',k=1,
                 baseline_testes=r/'absent.json',somente_preflight=True,dry_run=False,estrategias=['P1','P2'],diagnosticos=[],semgrep_bin='fake')
            def scanner(wt,profile,path,exe):
                amp.salvar(path,{'results':[]})
                return scan([finding()])
            with patch.object(amp,'RAIZ_REPO',r),patch.object(amp,'head',return_value='a'*40),patch.object(amp,'limpo',return_value=True),\
                 patch.object(amp,'carregar_perfil',return_value=profile),patch.object(amp,'conferir_versao',return_value='fake'),patch.object(amp,'scan_perfil',side_effect=scanner),\
                 patch.object(amp,'carregar_scan_perfil',return_value=scan([finding()])),\
                 patch('pipeline.llm.openai_client.ConfigLLM.do_env',side_effect=AssertionError('API não pode ser criada')):
                self.assertIsNone(amp.preparar(args,catalog,[case]))
                self.assertFalse((wt/'node_modules').exists())
                self.assertEqual((wt/'a.ts').read_text(),'let a=1\n')
                self.assertEqual(len(list((args.saida/'prompts').glob('*.json'))),2)
                self.assertIsNone(amp.preparar(args,catalog,[case]))
                args.estrategias=['P1']
                with self.assertRaisesRegex(ValueError,'Contrato incompatível'):amp.preparar(args,catalog,[case])

    def test_attempt_provenance_and_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'resultados_consolidados/execucoes.jsonl';p.parent.mkdir()
            p.write_text(json.dumps({'contrato_execucao_sha256':'bad'})+'\n')
            with self.assertRaisesRegex(ValueError,'contrato'):amp.conferir_linhas(p,'expected')


class ProvenienciaMetricasTests(unittest.TestCase):
    def test_artifact_corruption_and_truncated_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);artifact=root/'prompt.json';artifact.write_text('{}')
            rows=root/'resultados_consolidados/execucoes.jsonl';rows.parent.mkdir()
            row={'tentativa_id':'AMP_test','commit_alvo':'a'*40,'contrato_execucao_sha256':'hash',
                 'artefatos_sha256':{'prompt.json':digest(artifact)}}
            rows.write_text(json.dumps(row)+'\n')
            amp.conferir_linhas(rows,'hash')
            artifact.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'alterado'):amp.conferir_linhas(rows,'hash')
            rows.write_text('{partial')
            with self.assertRaisesRegex(ValueError,'corrompido'):amp.conferir_linhas(rows,'hash')

    def test_metrics_keep_unknowns_out_of_measured_rates(self):
        from scripts.reports.metricas_execucao import indices, normalizar
        row={'assinatura_ocorrencia':'x','R':None,'M':None,'F':1,'F_sem_separacao':1,
             'F_marcador':1,'F_criterio':1,'status_aplicacao':'aplicado',
             **{f'classificacao_{d}':'indeterminada_sast' for d in ('sem_separacao','marcador','criterio')},
             'testes_falhos_d_criterio':[]}
        result=indices([normalizar(row)],'criterio')
        self.assertEqual(result['TRV'],0)
        self.assertIsNone(result['TRI'])
        self.assertIsNone(result['TNINI'])
        self.assertEqual(result['indeterminadas'],1)
        self.assertEqual(result['denominadores_medidos'],{'R':0,'F_criterio':1,'M':0})

    def test_simulations_are_not_counted_as_api_calls(self):
        from scripts.reports.metricas_execucao import custos
        result=custos([{'dry_run':True,'modelo':'dry-run','do_cache':False,'custo_usd':0,'tokens_entrada':0,'tokens_saida':0}])
        self.assertEqual(result['chamadas_reais'],0)
        self.assertEqual(result['do_cache'],0)
        self.assertEqual(result['simuladas'],1)
        self.assertEqual(result['usd'],0)

    def test_diagnostics_are_portable_and_ids_strict(self):
        from pipeline.sast.semgrep_client import carregar_scan_perfil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);profile=SimpleNamespace(dados={'id_regras':['tcc.example']},no_escopo=lambda p:True)
            raw={'version':'1.177.0','results':[{'check_id':'tcc.example','path':str(root/'a.ts'),
                 'start':{'line':1,'col':1},'end':{'line':1,'col':2},'extra':{}}],
                 'errors':[{'type':'Syntax','location':{'path':str(root/'other.ts')},'message':str(root/'other.ts')}]}
            path=root/'raw.json';path.write_text(json.dumps(raw))
            result=carregar_scan_perfil(path,root,profile)
            self.assertEqual(result.findings[0].path,'a.ts')
            self.assertEqual(result.diagnosticos[0]['location']['path'],'other.ts')
            raw['results'][0]['check_id']='unknown';path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError,'ID não declarado'):carregar_scan_perfil(path,root,profile)


if __name__=='__main__':unittest.main()
