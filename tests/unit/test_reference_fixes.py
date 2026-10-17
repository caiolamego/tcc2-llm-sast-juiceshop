"""Transformações de referências pedagógicas; sem Semgrep, LLM ou alvo real."""
from pathlib import Path
import tempfile
import unittest
from scripts.audit.evaluate_reference_fixes import aplicar_trecho, interno


class ReferenceFixTests(unittest.TestCase):
    def test_preserva_contexto_imports_e_marcadores(self):
        before=b'import x from "x"\n// vuln-code-snippet start example\nold();\n// vuln-code-snippet end example\nfinish();\n'
        got=aplicar_trecho(before,b'new();',{'inicio':2,'fim':4})
        self.assertEqual(got,b'import x from "x"\n// vuln-code-snippet start example\nnew();\n// vuln-code-snippet end example\nfinish();\n')
        self.assertIn(b'old();',before)

    def test_nao_inventa_adaptacoes_de_nomes_ou_imports(self):
        before=b'// vuln-code-snippet start x\nold();\n// vuln-code-snippet end x\n'
        got=aplicar_trecho(before,b'models.User;\r\n',{'inicio':1,'fim':3})
        self.assertIn(b'models.User;',got)
        self.assertNotIn(b'import',got)

    def test_recusa_limites_inline_e_vazio(self):
        for original,ref,bounds in [
            (b'// vuln-code-snippet start x\na\n// vuln-code-snippet end x\n',b'',{'inicio':1,'fim':3}),
            (b'call(); // vuln-code-snippet start x\na\n// vuln-code-snippet end x\n',b'b',{'inicio':1,'fim':3}),
            (b'a\nb\n',b'b',{'inicio':1,'fim':99})]:
            with self.subTest(original=original),self.assertRaises(ValueError):aplicar_trecho(original,ref,bounds)

    def test_recusa_fonte_ausente_e_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for nome in ('ausente.ts','../fora.ts'):
                with self.assertRaises(ValueError):interno(root,nome)


if __name__=='__main__':unittest.main()
