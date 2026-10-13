
# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1].parent / "scripts"))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import copy
import json
import unittest

from scripts.reports.report_rodada2 import resumir
from scripts.reports.report_rodada3 import NEW, OLD, PERFIS


class Round3ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads(OLD.read_text(encoding="utf-8"))
        cls.new = json.loads(NEW.read_text(encoding="utf-8"))

    def test_resultados_e_historico(self):
        r = resumir(self.old, self.new, novo_scan="rodada3", perfis=PERFIS)
        self.assertEqual((r["alertas_novos"], r["alertas_perfil_ampliado"]), (1, 45))
        self.assertEqual((r["desafios_confirmados_antes"], r["desafios_confirmados_depois"]), (22, 23))
        self.assertEqual(r["novos_desafios_confirmados"], ["resetPasswordMortyChallenge"])

    def test_falha_se_triagem_anterior_muda(self):
        depois = copy.deepcopy(self.new)
        depois["alertas"][0]["triagem"]["status"] = "pendente"
        with self.assertRaisesRegex(ValueError, "historica mudou"):
            resumir(self.old, depois, novo_scan="rodada3", perfis=PERFIS)


if __name__ == "__main__":
    unittest.main()
