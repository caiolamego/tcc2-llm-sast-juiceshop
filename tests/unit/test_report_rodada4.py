
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
from scripts.reports.report_rodada4 import NEW, OLD, PERFIS


class Round4ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads(OLD.read_text(encoding="utf-8"))
        cls.new = json.loads(NEW.read_text(encoding="utf-8"))

    def test_contagens_e_novas_associacoes(self):
        r = resumir(self.old, self.new, novo_scan="rodada4", perfis=PERFIS)
        self.assertEqual((r["alertas_novos"], r["alertas_perfil_ampliado"]), (6, 51))
        self.assertEqual(r["triagem_novos"], {"confirmado": 5, "falso_positivo": 1})
        self.assertEqual((r["desafios_confirmados_antes"], r["desafios_confirmados_depois"]), (23, 28))
        self.assertEqual(r["novos_desafios_confirmados"],
                         ["fileWriteChallenge", "noSqlCommandChallenge", "noSqlOrdersChallenge",
                          "ssrfChallenge", "xxeFileDisclosureChallenge"])

    def test_nao_aceita_modificacao_de_scan_antigo(self):
        novo = copy.deepcopy(self.new)
        novo["resumo_scans"]["rodada3"]["sha256_json"] = "alterado"
        with self.assertRaisesRegex(ValueError, "historico alterado"):
            resumir(self.old, novo, novo_scan="rodada4", perfis=PERFIS)


if __name__ == "__main__":
    unittest.main()
