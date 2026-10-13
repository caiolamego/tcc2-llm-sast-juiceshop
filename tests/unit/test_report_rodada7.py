
# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1].parent / "scripts"))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import copy
import json
import unittest

from scripts.reports.report_rodada7 import NEW, OLD, comparar


class Round7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads(OLD.read_text(encoding="utf-8"))
        cls.new = json.loads(NEW.read_text(encoding="utf-8"))

    def test_contagens(self):
        r = comparar(self.old, self.new)
        self.assertEqual((r["alertas_novos"], r["alertas_perfil_ampliado"]), (5, 64))
        self.assertEqual(r["triagem_novos"], {"confirmado": 2, "falso_positivo": 3})
        self.assertEqual(r["triagem_perfil_ampliado"],
                         {"confirmado": 43, "falso_positivo": 19, "inconclusivo": 2})
        self.assertEqual((r["desafios_confirmados_antes"], r["desafios_confirmados_depois"]), (35, 37))
        self.assertEqual(r["novos_desafios_confirmados"], ["forgedReviewChallenge", "freeDeluxeChallenge"])
        self.assertEqual(r["avisos_parsing_novos"], 0)

    def test_alertas_antigos_e_baseline_intactos(self):
        antigos = {a["id"]: a for a in self.old["alertas"]}
        atuais = {a["id"]: a for a in self.new["alertas"]}
        for identidade, alerta in antigos.items():
            self.assertEqual(atuais[identidade], alerta)

    def test_preserva_proveniencia_ssti(self):
        novo = copy.deepcopy(self.new)
        novo.pop("revisoes_associacoes")
        with self.assertRaisesRegex(ValueError, "SSTI alterado"):
            comparar(self.old, novo)

    def test_falsos_positivos_nao_ampliam_cobertura(self):
        falsos = [a for a in self.new["alertas"]
                  if a["scan"] == "rodada7" and a["triagem"]["status"] == "falso_positivo"]
        self.assertEqual(len(falsos), 3)
        self.assertTrue(all(not a["triagem"]["desafios_confirmados"] for a in falsos))


if __name__ == "__main__":
    unittest.main()
