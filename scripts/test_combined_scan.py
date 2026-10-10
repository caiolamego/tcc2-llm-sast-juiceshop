import hashlib
import json
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parent.parent / 'outputs/auditoria_sast/combinado-hZGD7r'


class CombinedTests(unittest.TestCase):
    def test_totals_and_unique_keys(self):
        result = json.loads((BASE / 'triagem-final/resumo.json').read_text())
        self.assertEqual(result['alertas_brutos'], 124)
        self.assertEqual(result['triagem'], {'confirmado': 55, 'falso_positivo': 21, 'inconclusivo': 2, 'fora_escopo': 46})
        self.assertEqual(sum(result['triagem'].values()), 124)
        challenges = json.loads((BASE / 'triagem-final/matriz_desafios.json').read_text())
        self.assertEqual(len(challenges), 113)
        self.assertEqual(len({d['key'] for d in challenges}), 113)
        self.assertEqual(sum(d['confirmacao'] == 'confirmado' for d in challenges), 50)
        self.assertEqual(result['novos_desafios_confirmados'], [])
        self.assertEqual(result['anteriores_nao_reencontrados'], [])
        self.assertEqual(hashlib.sha256((BASE / 'scan.json').read_bytes()).hexdigest(), result['scan_sha256'])

    def test_scope_and_evidence(self):
        alerts = json.loads((BASE / 'triagem-final/alertas_classificados.json').read_text())
        for a in alerts:
            if a['status'] != 'confirmado':
                self.assertEqual(a['desafios'], [])
            if a['status'] == 'confirmado' and not a['referencias_historicas']:
                self.assertEqual((a['arquivo'], a['inicio']), ('routes/userProfile.ts', 61))
        self.assertEqual(sum(a['arquivo'].startswith('data/static/codefixes/') for a in alerts if a['status'] == 'fora_escopo'), 31)


if __name__ == '__main__':
    unittest.main()
