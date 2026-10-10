import copy
import json
import unittest

from report_rodada2 import resumir
from report_rodada6 import NEW, OLD, PERFIS, comparar


class Round6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads(OLD.read_text(encoding="utf-8"))
        cls.new = json.loads(NEW.read_text(encoding="utf-8"))

    def test_contagens_e_origem_da_cobertura(self):
        r = comparar(self.old, self.new)
        self.assertEqual((r["alertas_novos"], r["alertas_perfil_ampliado"]), (3, 59))
        self.assertEqual(r["triagem_novos"], {"confirmado": 3})
        self.assertEqual(r["triagem_perfil_ampliado"],
                         {"confirmado": 41, "falso_positivo": 16, "inconclusivo": 2})
        self.assertEqual((r["desafios_confirmados_antes"], r["desafios_confirmados_depois"]), (31, 35))
        self.assertEqual(r["novos_desafios_apenas_por_revisao"], ["sstiChallenge"])
        self.assertEqual(r["novos_desafios_por_alertas_novos"],
                         ["basketManipulateChallenge", "captchaBypassChallenge", "changePasswordBenderChallenge"])

    def test_revisao_exige_autorizacao_explicita(self):
        with self.assertRaisesRegex(ValueError, "triagem historica mudou"):
            resumir(self.old, self.new, novo_scan="rodada6", perfis=PERFIS)

    def test_baseline_intacto(self):
        self.assertEqual([a for a in self.old["alertas"] if a["scan"] == "baseline"],
                         [a for a in self.new["alertas"] if a["scan"] == "baseline"])

    def test_rejeita_mudancas_fora_da_revisao(self):
        for field, value in [("inicio", 62), ("severidade", "INFO")]:
            novo = copy.deepcopy(self.new)
            alerta = next(a for a in novo["alertas"] if a["id"] == "c1fb5ed14fbf04bb")
            alerta[field] = value
            with self.assertRaisesRegex(ValueError, "triagem historica mudou"):
                comparar(self.old, novo)

    def test_rejeita_proveniencia_forjada(self):
        novo = copy.deepcopy(self.new)
        novo["revisoes_associacoes"][0]["motivo"] = "modificado"
        with self.assertRaisesRegex(ValueError, "Historico de revisoes"):
            comparar(self.old, novo)

    def test_rejeita_linha_duplicada_na_matriz(self):
        novo = copy.deepcopy(self.new)
        novo["desafios"].append(novo["desafios"][0])
        with self.assertRaisesRegex(ValueError, "113 desafios"):
            comparar(self.old, novo)


if __name__ == "__main__":
    unittest.main()
