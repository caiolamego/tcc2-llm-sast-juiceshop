"""Contratos Docker e cópias interrompidas, sem Docker/serviços/LLM nos testes."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
def load(name):
    spec=importlib.util.spec_from_file_location('docker_'+name,ROOT/'docker'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
r=load('referencia');w=load('workspace')


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'reference';self.source.mkdir()
        (self.source/'a').write_text('completo');(self.source/'sub').mkdir()
        (self.source/'sub'/'b').write_text('b');self.dest=self.root/'work'/'node_modules'
        self.expected=w.fingerprint(self.source)
    def test_copia_completa_e_idempotente(self):
        self.assertEqual(w.copy_verified(self.source,self.dest,self.expected,self.root),'copiado')
        self.assertEqual(w.fingerprint(self.dest),self.expected)
        self.assertEqual(w.copy_verified(self.source,self.dest,self.expected,self.root),'conferido')
    def test_parcial_recusada_sem_sobrescrita(self):
        self.dest.mkdir(parents=True);(self.dest/'a').write_text('parcial')
        with self.assertRaisesRegex(ValueError,'incompleta'):w.copy_verified(self.source,self.dest,self.expected,self.root)
        self.assertEqual((self.dest/'a').read_text(),'parcial')
    def test_reparo_preserva_anterior(self):
        self.dest.mkdir(parents=True);(self.dest/'a').write_text('parcial')
        w.copy_verified(self.source,self.dest,self.expected,self.root,True)
        self.assertEqual(w.fingerprint(self.dest),self.expected)
        backups=list((self.root/'.recuperacao').glob('*/node_modules/a'))
        self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_text(),'parcial')
    def test_falha_na_copia_nao_promove_parcial(self):
        def fail(src,dest,**kw):
            dest.mkdir();(dest/'a').write_text('parcial');raise OSError('disco cheio')
        with patch.object(w.shutil,'copytree',side_effect=fail):
            with self.assertRaises(OSError):w.copy_verified(self.source,self.dest,self.expected,self.root)
        self.assertFalse(self.dest.exists());self.assertFalse(list(self.dest.parent.glob('.preparacao-*')))
    def test_falha_reparo_preserva_destino_ate_copia_verificada(self):
        self.dest.mkdir(parents=True);(self.dest/'local').write_text('preservar')
        with patch.object(w.shutil,'copytree',side_effect=OSError('disco cheio')):
            with self.assertRaises(OSError):w.copy_verified(self.source,self.dest,self.expected,self.root,True)
        self.assertEqual((self.dest/'local').read_text(),'preservar')
    def test_entrada_alterada_antes_da_promocao(self):
        with self.assertRaises(ValueError):w.copy_verified(self.source,self.dest,'0'*64,self.root)
        self.assertFalse(self.dest.exists())
    def test_hash_independe_de_diretorio_e_detecta_bytes_e_permissoes(self):
        w.copy_verified(self.source,self.dest,self.expected,self.root)
        (self.dest/'a').chmod(0o700);self.assertNotEqual(w.fingerprint(self.dest),self.expected)
    def test_link_externo_recusado(self):
        (self.source/'externo').symlink_to(self.root/'fora')
        with self.assertRaises(ValueError):w.fingerprint(self.source)
    def test_link_interno_preservado(self):
        (self.source/'link').symlink_to('a');h=w.fingerprint(self.source)
        w.copy_verified(self.source,self.dest,h,self.root)
        self.assertTrue((self.dest/'link').is_symlink());self.assertEqual(w.fingerprint(self.dest),h)


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for p in r.INPUTS:
            f=self.root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('fixture')
        self.baseline=self.root/'outputs/base/baseline_testes.json';self.baseline.parent.mkdir(parents=True)
        evidence=self.baseline.parent/'grupo/resultado.json';evidence.parent.mkdir();evidence.write_text('{}')
        self.data={'schema_versao':'2.0','status':'concluido','chamadas_llm':0,
                   'artefatos_sha256':{'grupo/resultado.json':r.digest(evidence)}}
        self.baseline.write_text(json.dumps(self.data))
        self.report={'commit_alvo_igual':True,'cobertura_igual':True,'grupos_total':39,'grupos_equivalentes':39,
                     'compilacoes':{'servidor':[True,True],'frontend':[True,True]},
                     'docker':{'sha256':r.digest(self.baseline)}}
        self.report_path=self.root/'outputs/comparacao.json';self.report_path.write_text(json.dumps(self.report))
        self.ref={'schema_versao':'1.0','imagem_id':'sha256:'+'a'*64,'plataforma':'linux/amd64',
                  'baseline':'outputs/base/baseline_testes.json','baseline_sha256':r.digest(self.baseline),
                  'artefatos_sha256':self.data['artefatos_sha256'],
                  'entradas_sha256':{p:r.digest(self.root/p) for p in r.INPUTS},
                  'comparacao':'outputs/comparacao.json','comparacao_sha256':r.digest(self.report_path)}
    def test_referencia_valida(self):self.assertEqual(r.validate(self.ref,self.root),self.data)
    def test_baseline_adulterado(self):
        self.baseline.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Baseline oficial alterado'):r.validate(self.ref,self.root)
    def test_evidencia_adulterada(self):
        (self.baseline.parent/'grupo/resultado.json').write_text('alterado')
        with self.assertRaisesRegex(ValueError,'Evidência alterada'):r.validate(self.ref,self.root)
    def test_entrada_modificada_exige_nova_versao(self):
        (self.root/'Dockerfile').write_text('outro ambiente')
        with self.assertRaisesRegex(ValueError,'nova referência'):r.validate(self.ref,self.root)
    def test_baseline_parcial_recusado(self):
        self.data['status']='parcial';self.baseline.write_text(json.dumps(self.data))
        self.ref['baseline_sha256']=r.digest(self.baseline)
        with self.assertRaisesRegex(ValueError,'incompleto'):r.validate(self.ref,self.root)
    def test_escape_e_symlink(self):
        for path in ('../fora','/tmp/fora'):
            with self.assertRaises(ValueError):r.local(path,self.root)
        with tempfile.TemporaryDirectory() as other:
            (self.root/'link').symlink_to(other)
            with self.assertRaises(ValueError):r.local('link/arquivo',self.root)
    def test_divergencia_funcional_bloqueia_congelamento(self):
        report=copy.deepcopy(self.report);report['grupos_equivalentes']=38
        self.assertFalse(r.equivalent(report))
    def test_comparacao_de_outro_baseline_recusada(self):
        self.report['docker']['sha256']='0'*64;self.report_path.write_text(json.dumps(self.report))
        self.ref['comparacao_sha256']=r.digest(self.report_path)
        with self.assertRaisesRegex(ValueError,'não pertence'):r.validate(self.ref,self.root)
    def test_publicacao_sem_sobrescrita(self):
        path=self.root/'ref.json';r.publish(path,self.ref);before=path.read_bytes()
        with self.assertRaises(ValueError):r.publish(path,{})
        self.assertEqual(path.read_bytes(),before)
    def test_lock_concorrente_preservado(self):
        path=self.root/'ref.json';lock=self.root/'ref.json.lock';lock.write_text('outro processo')
        with self.assertRaises(FileExistsError):r.publish(path,self.ref)
        self.assertEqual(lock.read_text(),'outro processo')
    def test_json_duplicado_recusado(self):
        path=self.root/'dup.json';path.write_text('{"a":1,"a":2}')
        with self.assertRaises(ValueError):r.read(path)
    def test_imagem_arm_recusada(self):
        with patch.object(r.subprocess,'check_output',return_value=json.dumps([{'Architecture':'arm64','Os':'linux','Id':'id'}])):
            with self.assertRaisesRegex(ValueError,'amd64'):r.image_id('fake')

if __name__=='__main__':unittest.main()
