
# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1].parent / "scripts"))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import copy
import json
import unittest
from scripts.reports.report_rodada8 import ROOT, OLD, NEW, ALVOS, comparar


class Round8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads(OLD.read_text())
        cls.new = json.loads(NEW.read_text())

    def test_counts(self):
        r = comparar(self.old, self.new)
        self.assertEqual((r["alertas_novos"], r["alertas_perfil_ampliado"]), (4, 68))
        self.assertEqual(r["triagem_novos"], {"confirmado": 4})
        self.assertEqual(r["triagem_perfil_ampliado"], {"confirmado": 47, "falso_positivo": 19, "inconclusivo": 2})
        self.assertEqual((r["desafios_confirmados_antes"], r["desafios_confirmados_depois"]), (37, 41))
        self.assertEqual(set(r["candidatos_incluidos"]), ALVOS)
        self.assertEqual(r["avisos_parsing_novos"], 0)

    def test_no_inflated_mapping(self):
        new = [a for a in self.new["alertas"] if a["scan"] == "rodada8"]
        history = next(a for a in new if a["arquivo"] == "routes/orderHistory.ts")
        self.assertEqual(history["triagem"]["desafios_confirmados"], [])
        crud = next(a for a in new if a["arquivo"] == "server.ts")
        self.assertEqual(set(crud["triagem"]["desafios_confirmados"]), {"registerAdminChallenge", "forgedFeedbackChallenge"})

    def test_old_alerts_immutable(self):
        current = {a["id"]: a for a in self.new["alertas"]}
        for old in self.old["alertas"]:
            self.assertEqual(current[old["id"]], old)
        changed = copy.deepcopy(self.new)
        changed["alertas"][0]["inicio"] += 1
        with self.assertRaises(ValueError):
            comparar(self.old, changed)


    def test_repeated_scan_equivalent(self):
        original = json.loads((ROOT / "outputs/auditoria_sast/rodada8.json").read_text())
        repeated = json.loads((NEW.parent / "repeticao/rodada8.json").read_text())
        def findings(scan):
            return sorted((r["check_id"], r["path"], r["start"]["line"],
                           r["start"]["col"], r["end"]["line"], r["end"]["col"])
                          for r in scan["results"])
        self.assertEqual(findings(original), findings(repeated))
        self.assertEqual(original.get("errors", []), [])
        self.assertEqual(repeated.get("errors", []), [])


if __name__ == "__main__":
    unittest.main()
