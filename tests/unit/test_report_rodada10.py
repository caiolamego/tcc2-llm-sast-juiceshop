
# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1].parent / "scripts"))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import copy
import hashlib
import json
import unittest
from scripts.reports.report_rodada10 import ROOT, OLD, NEW, ALVOS, comparar


class Round10Tests(unittest.TestCase):
    def test_counts_and_history(self):
        old, new = json.loads(OLD.read_text()), json.loads(NEW.read_text())
        result = comparar(old, new)
        self.assertEqual((result["alertas_novos"], result["alertas_perfil_ampliado"]), (2, 74))
        self.assertEqual(result["triagem_novos"], {"confirmado": 2})
        self.assertEqual(result["triagem_perfil_ampliado"], {"confirmado": 51, "falso_positivo": 21, "inconclusivo": 2})
        self.assertEqual((result["desafios_confirmados_antes"], result["desafios_confirmados_depois"]), (43, 45))
        self.assertEqual(set(result["candidatos_incluidos"]), ALVOS)
        self.assertEqual(len(result["prioritarios_fixos"]), 10)
        self.assertEqual(len(result["prioritarios_confirmados"]), 8)
        self.assertTrue(result["meta_7_de_10_atingida"])
        changed = copy.deepcopy(new)
        changed["alertas"][0]["inicio"] += 1
        with self.assertRaises(ValueError):
            comparar(old, changed)

    def test_repeat_and_provenance(self):
        def findings(scan):
            return sorted((r["check_id"], r["path"], r["start"]["line"], r["start"]["col"], r["end"]["line"], r["end"]["col"]) for r in scan["results"])
        first = None
        for base in (ROOT / "outputs/auditoria_sast", NEW.parent / "repeticao"):
            raw = (base / "rodada10.json").read_bytes()
            scan = json.loads(raw)
            manifest = json.loads((base / "manifesto-rodada10.json").read_text())
            self.assertEqual(scan.get("errors", []), [])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest["scan_sha256"])
            self.assertEqual(manifest["timeout_por_regra_segundos"], 30)
            for rule, expected in manifest["regras_sha256"].items():
                self.assertEqual(hashlib.sha256((ROOT / "rules/rodada10" / rule).read_bytes()).hexdigest(), expected)
            if first is not None:
                self.assertEqual(findings(scan), first)
            first = findings(scan)

    def test_mechanism_evidence(self):
        base = NEW.parent / "testes"
        manifest = json.loads((base / "manifesto.json").read_text())
        self.assertEqual(manifest["exit_code"], 0)
        self.assertEqual(hashlib.sha256((ROOT / "tests/integration/historico/test_rodada10_flows.mjs").read_bytes()).hexdigest(), manifest["teste_sha256"])
        self.assertEqual(hashlib.sha256((base / "dependencias/package-lock.json").read_bytes()).hexdigest(), manifest["lock_sha256"])
        self.assertIn('# pass 4', (base / "testes.tap").read_text())


if __name__ == "__main__":
    unittest.main()
