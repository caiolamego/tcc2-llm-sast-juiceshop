#!/usr/bin/env python3
"""Testes locais do vinculo alerta/desafio, sem alterar artefatos do TCC."""

# Permite execução direta sem depender do diretório corrente.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1].parent / "scripts"))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO  # noqa: E402

import unittest

from scripts.auditoria.gerar_matriz_desafios import aplicar_triagem, relacao


class RelacaoTests(unittest.TestCase):
    def setUp(self):
        self.blocos = [{"arquivo": "app.ts", "inicio": 10, "fim": 20,
                        "linhas_vulneraveis": [14, 17]}]

    def test_linha_vulneravel_tem_prioridade(self):
        self.assertEqual(relacao({"arquivo": "app.ts", "inicio": 13, "fim": 15}, self.blocos),
                         "linha_vulneravel")

    def test_bloco_nao_e_linha_vulneravel(self):
        self.assertEqual(relacao({"arquivo": "app.ts", "inicio": 11, "fim": 11}, self.blocos),
                         "bloco_marcado")

    def test_mesmo_arquivo_nao_confirma_desafio(self):
        self.assertEqual(relacao({"arquivo": "app.ts", "inicio": 50, "fim": 50}, self.blocos),
                         "mesmo_arquivo_suspeita")

    def test_outro_arquivo_nao_associa(self):
        self.assertIsNone(relacao({"arquivo": "outro.ts", "inicio": 14, "fim": 14}, self.blocos))

    def test_triagem_pendente_por_padrao(self):
        alertas = [{"regra": "x", "arquivo": "app.ts", "inicio": 14}]
        aplicar_triagem(alertas, [], {"challenge"})
        self.assertEqual(alertas[0]["triagem"]["status"], "pendente")

    def test_triagem_desatualizada_falha(self):
        with self.assertRaisesRegex(ValueError, "sem alerta correspondente"):
            aplicar_triagem([], [{"regra": "x", "arquivo": "app.ts", "linha": 14,
                                 "status": "confirmado", "desafios": ["challenge"],
                                 "motivo": "teste"}], {"challenge"})


if __name__ == "__main__":
    unittest.main()
