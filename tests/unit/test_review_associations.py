
# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1].parent / "scripts"))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import copy
import unittest

from scripts.audit.review_associations import aplicar_revisoes


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.alertas = [{"id": "a", "scan": "default", "triagem": {
            "status": "confirmado", "motivo": "revisao original",
            "desafios_confirmados": ["old"], "sem_marcador": True}}]
        self.revisao = {"alerta_id": "a", "triagem_anterior": copy.deepcopy(self.alertas[0]["triagem"]),
                        "desafios_adicionais": ["new"], "motivo": "evidencia nova"}

    def test_adicao_com_historico(self):
        log = aplicar_revisoes(self.alertas, [self.revisao], {"old", "new"})
        self.assertEqual(log[0]["triagem_anterior"], self.revisao["triagem_anterior"])
        self.assertEqual(self.alertas[0]["triagem"]["desafios_confirmados"], ["old", "new"])

    def test_nao_muda_baseline(self):
        self.alertas[0]["scan"] = "baseline"
        with self.assertRaisesRegex(ValueError, "baseline"):
            aplicar_revisoes(self.alertas, [self.revisao], {"old", "new"})

    def test_nao_reclassifica_fp(self):
        self.alertas[0]["triagem"]["status"] = "falso_positivo"
        self.revisao["triagem_anterior"]["status"] = "falso_positivo"
        with self.assertRaisesRegex(ValueError, "nao confirmada"):
            aplicar_revisoes(self.alertas, [self.revisao], {"old", "new"})

    def test_rejeita_chave_desconhecida_ou_repetida(self):
        for adicionais in [["unknown"], ["old"], ["new", "new"], []]:
            revisao = {**self.revisao, "desafios_adicionais": adicionais}
            with self.assertRaisesRegex(ValueError, "invalidas"):
                aplicar_revisoes(self.alertas, [revisao], {"old", "new"})

    def test_rejeita_estado_anterior_divergente(self):
        self.revisao["triagem_anterior"]["motivo"] = "outro"
        with self.assertRaisesRegex(ValueError, "anterior divergente"):
            aplicar_revisoes(self.alertas, [self.revisao], {"old", "new"})


if __name__ == "__main__":
    unittest.main()
