#!/usr/bin/env python3
"""Invariantes da selecao exploratoria de casos de correcao."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1].parent / "scripts"))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import copy
import json
import unittest

import yaml

from scripts.audit.build_repair_candidates import CONFIG, MATRIX, construir


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matriz = json.loads(MATRIX.read_text(encoding="utf-8"))
        cls.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    def test_cobertura_e_colisoes(self):
        dados = construir(self.matriz, self.config)
        self.assertEqual((dados["total_casos"], dados["total_desafios"]), (16, 20))
        self.assertEqual(len(dados["colisoes_assinatura_legada"]), 3)
        self.assertTrue(all(c["status"] == "aguarda_teste_regressao" for c in dados["casos"]))

    def test_falso_positivo_nao_pode_entrar(self):
        config = copy.deepcopy(self.config)
        config["casos"][0]["alertas"] = ["default|routes/captcha.ts|22"]
        with self.assertRaisesRegex(ValueError, "nao confirmado"):
            construir(self.matriz, config)

    def test_desafio_nao_pode_ser_contado_duas_vezes(self):
        config = copy.deepcopy(self.config)
        config["casos"][1]["desafios"].append("loginAdminChallenge")
        with self.assertRaisesRegex(ValueError, "duplicados"):
            construir(self.matriz, config)


if __name__ == "__main__":
    unittest.main()
