"""Integridade das revisões e dos fontes arquivados, sem executar o alvo."""
import copy
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
import yaml
from pipeline.sast.associacoes import carregar
from scripts.audit.recompare_archived_scans import conferir_patch, local


class EvidenceTests(unittest.TestCase):
    def test_patch_correspondence_and_tampering(self):
        before=b'a\nb\nc\n';after=b'a\nnew\nc\n'
        patch=('diff --git a/a.ts b/a.ts\n'+''.join(difflib.unified_diff(
            before.decode().splitlines(True),after.decode().splitlines(True),fromfile='a/a.ts',tofile='b/a.ts'))).encode()
        conferir_patch(before,after,patch)
        for original,corrected,diff in ((before,after+b'x\n',patch),(b'wrong\nb\nc\n',after,patch),
                                         (before,after,patch+patch),(before,after,patch.replace(b'@@ -1',b'@@ -9'))):
            with self.subTest(diff=diff),self.assertRaises(ValueError):conferir_patch(original,corrected,diff)

    def test_insert_at_start_and_multiple_hunks(self):
        before=''.join(f'line{i}\n' for i in range(30));after='new\n'+before.replace('line25\n','changed\n')
        diff='diff --git a/a.ts b/a.ts\n'+''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True)))
        conferir_patch(before.encode(),after.encode(),diff.encode())

    def test_local_rejects_external_symlink_and_absent_file(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'inside';root.mkdir();(base/'outside').write_text('data')
            (root/'link').symlink_to(base/'outside')
            for name in ('../outside','link','missing'):
                with self.subTest(name=name),self.assertRaises(ValueError):local(root,name)

    def test_review_does_not_mutate_catalog_and_validates_evidence(self):
        catalog=ROOT/'outputs/catalogos/ampliado_v1/catalogo_issues.json'
        cases=json.loads(catalog.read_text());before=copy.deepcopy(cases);raw=catalog.read_bytes()
        revisions=carregar(ROOT/'config/revisoes_associacoes_v1.yaml',catalog,cases,ROOT)
        self.assertEqual(len(revisions['revisoes']),6)
        self.assertEqual(cases,before);self.assertEqual(raw,catalog.read_bytes())
        self.assertEqual(revisions['catalogo_sha256'],hashlib.sha256(raw).hexdigest())

    def test_duplicate_unknown_case_bad_hash_and_escape_are_rejected(self):
        catalog=ROOT/'outputs/catalogos/ampliado_v1/catalogo_issues.json'
        cases=json.loads(catalog.read_text())
        original=yaml.safe_load((ROOT/'config/revisoes_associacoes_v1.yaml').read_text())
        variants=[]
        bad=copy.deepcopy(original);bad['revisoes'].append(bad['revisoes'][0]);variants.append(bad)
        bad=copy.deepcopy(original);bad['revisoes'][0]['caso_id']='AMP_UNKNOWN';variants.append(bad)
        bad=copy.deepcopy(original);bad['catalogo_sha256']='0'*64;variants.append(bad)
        bad=copy.deepcopy(original);bad['revisoes'][0]['evidencia']='../outside';variants.append(bad)
        bad=copy.deepcopy(original);bad['revisoes'][0]['tipo']='confirmada_automaticamente';variants.append(bad)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'revisions.yaml'
            for bad in variants:
                path.write_text(yaml.safe_dump(bad))
                with self.subTest(bad=bad),self.assertRaises(ValueError):carregar(path,catalog,cases,ROOT)
            path.write_text('schema_versao: "1.0"\nschema_versao: "1.0"\n')
            with self.assertRaises(ValueError):carregar(path,catalog,cases,ROOT)

    def test_cli_help_outside_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            proc=subprocess.run([sys.executable,str(ROOT/'scripts/audit/recompare_archived_scans.py'),'--help'],
                                cwd=folder,capture_output=True,text=True,timeout=10)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertIn('--parser-checkout',proc.stdout)


if __name__=='__main__':unittest.main()
