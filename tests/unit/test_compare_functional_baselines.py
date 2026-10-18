"""Comparação de baselines funcionais usa só os JSONs; não executa testes nem o alvo."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit.compare_functional_baselines import comparar, main


def baseline():
    teste = {'id': 'test/api/a.test.ts :: s > t', 'estado': 'passou'}
    return {'schema_versao': '2.0', 'commit_alvo': 'c', 'cobertura': {'revisao_sha256': 'r'},
            'ambiente': {'node': 'v24', 'lock_sha256': 'l1', 'frontend': {'lock_sha256': 'f1'}},
            'compilacoes': {'servidor': {'passou': True}}, 'duracao_s': 10.0,
            'grupos': {'g': {'comparavel': True, 'testes': [teste], 'falhos': [],
                             'obrigatorios_aprovados': [teste['id']]}}}


class CompareFunctionalBaselinesTests(unittest.TestCase):
    def gravar(self, pasta, nome, dados):
        caminho = Path(pasta) / nome
        caminho.write_text(json.dumps(dados), encoding='utf-8')
        return caminho

    def test_equivalente_com_ambiente_diferente(self):
        with tempfile.TemporaryDirectory() as pasta:
            novo = baseline()
            novo['ambiente']['lock_sha256'] = 'l2'
            novo['ambiente']['frontend']['lock_sha256'] = 'f2'
            r = comparar(self.gravar(pasta, 'a.json', baseline()), self.gravar(pasta, 'b.json', novo))
            self.assertEqual(r['grupos_equivalentes'], 1)
            self.assertEqual(r['ambiente_diferente'], ['frontend.lock_sha256', 'lock_sha256'])

    def test_estado_diferente_quebra_equivalencia_e_retorna_2(self):
        with tempfile.TemporaryDirectory() as pasta:
            novo = deepcopy(baseline())
            g = novo['grupos']['g']
            g['testes'][0]['estado'] = 'falhou'
            g['falhos'] = [g['testes'][0]['id']]
            a, b = self.gravar(pasta, 'a.json', baseline()), self.gravar(pasta, 'b.json', novo)
            r = comparar(a, b)
            self.assertFalse(r['grupos']['g']['equivalente'])
            self.assertEqual(r['grupos']['g']['estado_diferente'], {g['testes'][0]['id']: ['passou', 'falhou']})
            saida = Path(pasta) / 'saida.json'
            self.assertEqual(main(['--referencia', str(a), '--novo', str(b), '--saida', str(saida)]), 2)
            self.assertTrue(saida.is_file())

    def test_grupo_ausente_nao_e_equivalente(self):
        with tempfile.TemporaryDirectory() as pasta:
            novo = baseline()
            novo['grupos'] = {}
            r = comparar(self.gravar(pasta, 'a.json', baseline()), self.gravar(pasta, 'b.json', novo))
            self.assertEqual(r['grupos_equivalentes'], 0)
            self.assertEqual(r['grupos']['g'], {'presente_piloto10': True, 'presente_docker': False})

    def test_recusa_destino_existente(self):
        with tempfile.TemporaryDirectory() as pasta:
            a = self.gravar(pasta, 'a.json', baseline())
            saida = self.gravar(pasta, 'saida.json', {'x': 1})
            self.assertEqual(main(['--referencia', str(a), '--novo', str(a), '--saida', str(saida)]), 1)
            self.assertEqual(json.loads(saida.read_text(encoding='utf-8')), {'x': 1})


if __name__ == '__main__':
    unittest.main()
