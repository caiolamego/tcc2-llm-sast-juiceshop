
# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1].parent / "scripts"))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402

import copy
import json
import unittest

from scripts.relatorios.relatorio_rodada2 import resumir
from scripts.relatorios.relatorio_rodada5 import NEW, OLD, PERFIS


class Round5ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads(OLD.read_text(encoding="utf-8"))
        cls.new = json.loads(NEW.read_text(encoding="utf-8"))

    def test_contagens_sem_inflar_cobertura(self):
        r = resumir(self.old, self.new, novo_scan="rodada5", perfis=PERFIS)
        self.assertEqual((r["alertas_novos"], r["alertas_perfil_ampliado"]), (5, 56))
        self.assertEqual(r["triagem_novos"],
                         {"confirmado": 3, "falso_positivo": 1, "inconclusivo": 1})
        self.assertEqual((r["desafios_confirmados_antes"], r["desafios_confirmados_depois"]), (28, 31))
        self.assertEqual(r["novos_desafios_confirmados"],
                         ["basketAccessChallenge", "rceChallenge", "rceOccupyChallenge"])
        order = next(a for a in self.new["alertas"]
                     if a["scan"] == "rodada5" and a["arquivo"] == "routes/order.ts")
        self.assertEqual(order["triagem"]["desafios_confirmados"], [])

    def test_nao_aceita_mudar_triagem_antiga(self):
        novo = copy.deepcopy(self.new)
        antigo = next(a for a in novo["alertas"] if a["scan"] == "rodada4")
        antigo["triagem"]["status"] = "inconclusivo"
        with self.assertRaisesRegex(ValueError, "triagem historica mudou"):
            resumir(self.old, novo, novo_scan="rodada5", perfis=PERFIS)


if __name__ == "__main__":
    unittest.main()
