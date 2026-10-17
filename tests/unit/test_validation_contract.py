"""Contrato 3.0 e reserva de worktrees sem execução do alvo."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from pipeline.metrics.loader import _validar_contrato
from pipeline.target.workspace import reservar_execucao, _RESERVAS
from pipeline.validation.components import componentes


def entrada():
    c={'schema_versao':'3.0','execucao':'TEST','modo':'preflight','commit_alvo':'commit',
       'hashes_catalogo':{},'casos':['AMP1'],'estrategias':['P1'],'diagnosticos':[],
       'comparador':'blocos_unicos_v1','validacao':{'politica_validacao':'historica_v1',
       'cache_validacao':'desligado','repeticao_api':'ampla',
       'implementacao':{'runner.py':'a'*64},'ambientes':[]}}
    return SimpleNamespace(contrato=c,execucao='TEST',catalogo=SimpleNamespace(commit='commit',hashes={},casos=[{'caso_id':'AMP1'}]))


class ValidationContractTests(unittest.TestCase):
    def test_comparadores_versionados_e_versao_desconhecida(self):
        for comparador in ('blocos_unicos_v1','ocorrencias_contexto_v2'):
            e=entrada();e.contrato['comparador']=comparador
            with self.subTest(comparador=comparador),patch('pipeline.metrics.loader._perfil'):
                _validar_contrato(e)
        e=entrada();e.contrato['comparador']='sem_identidade'
        with patch('pipeline.metrics.loader._perfil'),self.assertRaises(ValueError):_validar_contrato(e)

    def test_troca_de_comparador_recusa_retomada_antiga(self):
        from pipeline.execucao_ampliada import validar_compatibilidade_antiga
        old={'schema_versao':'1.0','comparador':'blocos_unicos_v1','estrategias':['P1'],
             'diagnosticos':[],'prompts_validacao_sha256':{}}
        current=dict(old,schema_versao='3.0',comparador='ocorrencias_contexto_v2',validacao={})
        with self.assertRaisesRegex(ValueError,'campos científicos'):
            validar_compatibilidade_antiga(old,current,Path('.'),[],Path('.'))

    def test_fingerprint_inclui_sast_comparador_e_restauracao(self):
        fontes=componentes()
        for nome in ('src/pipeline/sast/semgrep_client.py','src/pipeline/sast/comparacao.py',
                     'src/pipeline/target/workspace.py','src/pipeline/run_pipeline.py',
                     'src/pipeline/execucao_ampliada.py','config/conjunto_d.json'):
            self.assertIn(nome,fontes)
            self.assertEqual(len(fontes[nome]),64)

    def test_novo_e_antigos_continuam_legiveis(self):
        for versao in ('1.0','2.0','3.0'):
            e=entrada();e.contrato['schema_versao']=versao
            if versao!='3.0':e.contrato.pop('validacao')
            with self.subTest(versao=versao),patch('pipeline.metrics.loader._perfil'):
                _validar_contrato(e)

    def test_politica_nova_exige_mapa_e_hashes_validos(self):
        for campo,valor in (('implementacao',{}),('politica_validacao','otimizada_v1'),('cache_validacao','inventado')):
            e=entrada();e.contrato['validacao'][campo]=valor
            with self.subTest(campo=campo),patch('pipeline.metrics.loader._perfil'),self.assertRaises(ValueError):
                _validar_contrato(e)

    def test_contrato_relacionado_requer_hash_e_preserva_f_nulo(self):
        from pipeline.metrics.normalizer import normalizar
        from pipeline.metrics.calculator import metricas
        e = entrada()
        e.contrato['validacao']['politica_validacao'] = 'relacionada_v1'
        with patch('pipeline.metrics.loader._perfil'), self.assertRaises(ValueError):
            _validar_contrato(e)
        e.contrato['validacao']['mapa_testes_sha256'] = 'b'*64
        with patch('pipeline.metrics.loader._perfil'):
            _validar_contrato(e)
        row = {'R': 1, 'M': 1, 'F': None, 'status_aplicacao': 'aplicado'}
        for d in ('criterio', 'marcador', 'sem_separacao'):
            row['F_'+d] = None
            row['classificacao_'+d] = 'indeterminada_funcional'
        normalizado = normalizar(row)
        self.assertTrue(normalizado['incompleto_criterio'])
        self.assertIsNone(normalizado['F_criterio'])
        ms = metricas([normalizado], 'criterio', True)
        self.assertEqual(ms['TRV']['denominador'], 1)
        self.assertIsNone(ms['TPF']['valor'])

    def test_reserva_impede_segundo_processo_e_e_reentrante(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz=Path(tmp)
            reservar_execucao(raiz);reservar_execucao(raiz)
            try:
                fonte=Path(__file__).resolve().parents[2]/'src'
                codigo='import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from pipeline.target.workspace import reservar_execucao;reservar_execucao(Path(sys.argv[2]))'
                resultado=subprocess.run([sys.executable,'-c',codigo,str(fonte),tmp],capture_output=True,text=True,timeout=10)
                self.assertNotEqual(resultado.returncode,0)
                self.assertIn('Outra execução',resultado.stderr)
            finally:
                _RESERVAS.pop(str(raiz/'.cache')).close()


if __name__=='__main__':unittest.main()
