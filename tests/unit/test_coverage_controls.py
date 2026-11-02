"""Controles não podem aceitar falha de infraestrutura nem deixar o alvo mutado."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
spec = importlib.util.spec_from_file_location('coverage_controls', ROOT / 'scripts/experimento/validar_controles_cobertura.py')
controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controls)


class CoverageControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wt = self.root / 'target'
        self.wt.mkdir()
        self.source = self.wt / 'route.ts'
        self.original = b'return expected\n'
        self.source.write_bytes(self.original)
        self.specification = self.root / 'controls.json'
        self.control = {'id': 'control', 'grupo': 'group', 'arquivo': 'route.ts',
                        'antes': 'return expected', 'depois': 'return wrong', 'teste_esperado': 'keeps contract'}
        self.write_spec()
        self.args = SimpleNamespace(checkout=self.wt, catalogo=self.root / 'catalog.json',
                                    revisao=self.root / 'review.yaml', mapa_testes=self.root / 'map.yaml',
                                    controles=self.specification, saida=self.root / 'outputs/result')
        for target, value in [
            ('RAIZ_REPO', self.root), ('reservar_execucao', None),
            ('carregar_catalogo', SimpleNamespace(commit='fixed')),
            ('conferir_checkout', None),
        ]:
            p = patch.object(controls, target, return_value=value) if target != 'RAIZ_REPO' else patch.object(controls, target, value)
            p.start()
            self.addCleanup(p.stop)
        for target, value in [('carregar', {'grupos': {'group': {}}}), ('identidade', {'fixed': 'identity'})]:
            p = patch.object(controls.cobertura, target, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.healthy = {'comparavel': True, 'falhos': [], 'testes': [], 'falha_operacional': None}
        self.broken = {'comparavel': False, 'falhos': ['test :: suite > keeps contract'],
                       'testes': [{'nome': 'suite > keeps contract', 'estado': 'falhou'}], 'falha_operacional': None}

    def write_spec(self):
        self.specification.write_text(json.dumps({'schema_versao': '1.0', 'controles': [self.control]}))

    def report(self):
        return json.loads((self.args.saida / 'controles.json').read_text())

    def test_records_detection_and_restores_original_bytes(self):
        def runner(*args, **kwargs):
            return self.broken if self.source.read_bytes() != self.original else self.healthy
        with patch.object(controls, 'executar_grupo', side_effect=runner):
            controls.executar(self.args)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(self.report()['status'], 'concluido')
        self.assertTrue(self.report()['controles'][0]['restaurado'])

    def test_restores_source_even_when_runner_raises(self):
        with patch.object(controls, 'executar_grupo', side_effect=[self.healthy, RuntimeError('runner failed')]):
            with self.assertRaisesRegex(RuntimeError, 'runner failed'):
                controls.executar(self.args)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(self.report()['status'], 'parcial')

    def test_operational_failure_does_not_count_as_detection(self):
        broken = dict(self.broken, falha_operacional='timeout')
        with patch.object(controls, 'executar_grupo', side_effect=[self.healthy, broken]):
            with self.assertRaisesRegex(ValueError, 'não detectados'):
                controls.executar(self.args)
        self.assertFalse(self.report()['controles'][0]['detectado'])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_failure_of_unrelated_test_does_not_count_as_detection(self):
        broken = dict(self.broken, testes=[{'nome': 'suite > another test', 'estado': 'falhou'}])
        with patch.object(controls, 'executar_grupo', side_effect=[self.healthy, broken]):
            with self.assertRaisesRegex(ValueError, 'não detectados'):
                controls.executar(self.args)
        self.assertFalse(self.report()['controles'][0]['detectado'])

    def test_unhealthy_reference_never_mutates_target(self):
        with patch.object(controls, 'executar_grupo', return_value=self.broken):
            with self.assertRaisesRegex(ValueError, 'sadio não aprovado'):
                controls.executar(self.args)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_non_unique_anchor_rejected_before_any_test(self):
        self.source.write_bytes(self.original * 2)
        with patch.object(controls, 'executar_grupo') as runner:
            with self.assertRaisesRegex(ValueError, 'não é única'):
                controls.executar(self.args)
        runner.assert_not_called()
        self.assertFalse(self.args.saida.exists())

    def test_unknown_concurrent_edit_is_preserved(self):
        def runner(*args, **kwargs):
            if self.source.read_bytes() != self.original:
                self.source.write_text('independent edit\n')
                return self.broken
            return self.healthy
        with patch.object(controls, 'executar_grupo', side_effect=runner):
            with self.assertRaisesRegex(RuntimeError, 'alteração desconhecida'):
                controls.executar(self.args)
        self.assertEqual(self.source.read_text(), 'independent edit\n')


if __name__ == '__main__':
    unittest.main()
