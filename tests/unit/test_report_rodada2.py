
# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1].parent / "scripts"))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402

#!/usr/bin/env python3
import copy
import json
import unittest

from scripts.relatorios.relatorio_rodada2 import OLD, NEW, resumir


class Round2ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads(OLD.read_text(encoding="utf-8"))
        cls.new = json.loads(NEW.read_text(encoding="utf-8"))

    def test_contagens_e_desafios(self):
        r = resumir(self.old, self.new)
        self.assertEqual((r["alertas_novos"], r["alertas_perfil_ampliado"]), (4, 44))
        self.assertEqual((r["desafios_confirmados_antes"], r["desafios_confirmados_depois"]), (20, 22))
        self.assertEqual(r["novos_desafios_confirmados"],
                         ["exposedMetricsChallenge", "weakPasswordChallenge"])

    def test_nao_aceita_scan_historico_alterado(self):
        novo = copy.deepcopy(self.new)
        novo["resumo_scans"]["default"]["sha256_json"] = "alterado"
        with self.assertRaisesRegex(ValueError, "historico alterado"):
            resumir(self.old, novo)


if __name__ == "__main__":
    unittest.main()
