import copy
import hashlib
import json
import unittest
from report_rodada9 import ROOT, OLD, NEW, ALVOS, comparar


class Round9Tests(unittest.TestCase):
    def test_counts_and_history(self):
        old, new = json.loads(OLD.read_text()), json.loads(NEW.read_text())
        result = comparar(old, new)
        self.assertEqual((result["alertas_novos"], result["alertas_perfil_ampliado"]), (4, 72))
        self.assertEqual(result["triagem_novos"], {"confirmado": 2, "falso_positivo": 2})
        self.assertEqual(result["triagem_perfil_ampliado"], {"confirmado": 49, "falso_positivo": 21, "inconclusivo": 2})
        self.assertEqual((result["desafios_confirmados_antes"], result["desafios_confirmados_depois"]), (41, 43))
        self.assertEqual(set(result["candidatos_incluidos"]), ALVOS)
        changed = copy.deepcopy(new)
        changed["alertas"][0]["inicio"] += 1
        with self.assertRaises(ValueError):
            comparar(old, changed)

    def test_repeat_and_provenance(self):
        def findings(scan):
            return sorted((r["check_id"], r["path"], r["start"]["line"], r["start"]["col"], r["end"]["line"], r["end"]["col"]) for r in scan["results"])
        first = None
        for folder in ("scan_completo", "repeticao"):
            base = NEW.parent / folder
            raw = (base / "rodada9.json").read_bytes()
            scan = json.loads(raw)
            manifest = json.loads((base / "manifesto-rodada9.json").read_text())
            self.assertEqual(scan.get("errors", []), [])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest["scan_sha256"])
            self.assertEqual(manifest["timeout_por_regra_segundos"], 30)
            for rule, expected in manifest["regras_sha256"].items():
                self.assertEqual(hashlib.sha256((ROOT / "rules/rodada9" / rule).read_bytes()).hexdigest(), expected)
            if first is not None:
                self.assertEqual(findings(scan), first)
            first = findings(scan)

    def test_incomplete_attempt_preserved(self):
        base = ROOT / "outputs/auditoria_sast"
        initial = json.loads((base / "rodada9.json").read_text())
        self.assertTrue(any(e["type"] == "Timeout" and e["path"] == "server.ts" for e in initial["errors"]))
        manifest = json.loads((base / "manifesto-rodada9.json").read_text())
        archived = (NEW.parent / "tentativa_inicial/asymmetric-method-guard.yaml").read_bytes()
        self.assertEqual(hashlib.sha256(archived).hexdigest(), manifest["regras_sha256"]["asymmetric-method-guard.yaml"])


if __name__ == "__main__":
    unittest.main()
