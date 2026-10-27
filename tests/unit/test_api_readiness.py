"""Preparação local em fixtures, sem iniciar testes/servidores do alvo."""
from pathlib import Path
import tempfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))
import unittest
from unittest.mock import patch

from pipeline.etapas.e07_validacao import preparacao_api as api


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.target=self.root/'wt-4'
        self.target.mkdir()
        for name in (*api.OBRIGATORIOS,'frontend/dist/frontend/hacking-instructor-fixture.js'):
            p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)

    def test_copy_isolated_and_refuse_existing_mismatch(self):
        result=api.preparar(self.source,self.target)
        self.assertEqual(result['diretorios_criados'],['build','frontend/dist'])
        self.assertEqual(api.inventario(self.source),api.inventario(self.target))
        p=self.target/'frontend/dist/frontend/main.js';p.write_text('unknown')
        with self.assertRaisesRegex(ValueError,'substituição recusada'):api.preparar(self.source,self.target)
        self.assertEqual(p.read_text(),'unknown')

    def test_empty_missing_chunk_and_external_symlink(self):
        p=self.source/'frontend/dist/frontend/main.js';p.write_bytes(b'')
        with self.assertRaises(ValueError):api.conferir(self.source,False)
        p.unlink();p.symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):api.inventario(self.source)

    def test_busy_port_refused_without_services(self):
        with patch.object(api.socket,'socket') as factory:
            factory.return_value.__enter__.return_value.bind.side_effect=OSError('occupied')
            with self.assertRaisesRegex(ValueError,'Porta API indisponível'):api.conferir(self.source)

    def test_change_to_ignored_boot_asset_changes_identity(self):
        first=api.inventario(self.source)
        (self.source/'frontend/dist/frontend/main.js').write_text('changed')
        self.assertNotEqual(first,api.inventario(self.source))


if __name__=='__main__':unittest.main()
