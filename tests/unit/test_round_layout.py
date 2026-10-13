"""Confere disponibilidade e proveniência após a mudança dos testes Node."""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RoundLayoutTests(unittest.TestCase):
    def test_round_inventory_and_historical_sources(self):
        for number in range(1, 13):
            with self.subTest(rodada=number):
                folder = ROOT / f'tests/integration/rodada{number}'
                data = json.loads((folder / 'manifesto.json').read_text())
                self.assertEqual(data['rodada'], number)
                self.assertTrue((folder / 'README.md').is_file())
                self.assertTrue(list((ROOT / data['regras']).glob('*.yaml')))
                if data['teste_integracao'] is None:
                    self.assertEqual(data['status_integracao'], 'nao_implementado')
                    self.assertFalse((folder / 'test.mjs').exists())
                else:
                    original = (ROOT / data['fonte_historica']).read_bytes()
                    self.assertEqual(hashlib.sha256(original).hexdigest(), data['sha256_fonte_historica'])
                    current = (ROOT / data['teste_integracao']).read_text()
                    self.assertEqual(current, original.decode().replace("new URL('../outputs/", "new URL('../../../outputs/"))
