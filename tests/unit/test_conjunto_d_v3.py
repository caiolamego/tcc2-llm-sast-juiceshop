"""Conjunto D v3: critério (e) em todos os casos e critério (d) só nos casos ligados."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

RAIZ=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(RAIZ/'src'))
from pipeline.etapas.e07_validacao import conjunto_d as cd

ARQUIVO=RAIZ/'config/conjunto_d_cobertura_v3.json'
PUT='test/api/product.test.ts :: /api/Products/:id > PUT update existing product is possible due to Missing Function-Level Access Control vulnerability'
FEEDBACK='test/api/feedback.test.ts :: /api/Feedbacks > POST feedback is associated with current user'
PEDIDOS='test/api/order-history.test.ts :: /rest/order-history > GET own previous orders'


class ConjuntoDV3Tests(unittest.TestCase):
    def test_criterio_e_vale_em_qualquer_caso(self):
        for caso in ('AMP095fcc0f303ff032','AMPoutro',None):
            self.assertEqual(cd.criterio_de(PUT,ARQUIVO,caso),'e')

    def test_criterio_d_vale_so_nos_casos_ligados(self):
        self.assertEqual(cd.criterio_de(FEEDBACK,ARQUIVO,'AMP4d38adc404310ebe'),'d')
        self.assertIsNone(cd.criterio_de(FEEDBACK,ARQUIVO,'AMPoutro'))

    def test_teste_de_comportamento_legitimo_continua_em_f(self):
        self.assertIsNone(cd.criterio_de(PEDIDOS,ARQUIVO,'AMP0de5113d9249c2c3'))

    def test_marcador_nao_inclui_o_criterio_e(self):
        s=cd.classificar([PUT],ARQUIVO,'AMPoutro')
        self.assertEqual((s['d_marcador'],s['d_criterio'],s['f_criterio']),([],[PUT],[]))
        self.assertEqual(s['f_marcador'],[PUT])

    def test_nenhum_teste_fica_nas_duas_listas(self):
        dados=json.loads(ARQUIVO.read_text(encoding='utf-8'))
        globais={(d['arquivo'],d['nome']) for d in dados['d']}
        ligados={(d['arquivo'],d['nome']) for d in dados['por_caso']}
        self.assertFalse(globais&ligados)

    def test_criterio_desconhecido_e_recusado(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo=Path(pasta)/'d.json'
            arquivo.write_text(json.dumps({'schema_versao':'2.0','d':[{'arquivo':'a','nome':'b','criterio':'x'}]}),encoding='utf-8')
            with self.assertRaises(ValueError):
                cd.criterio_de('a :: b',arquivo)


if __name__=='__main__':
    unittest.main()
