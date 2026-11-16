"""Classificação posterior preserva fontes e resultados, mudando só os grupos."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from tests.unit.test_metrics import case, row, context, save
from pipeline.etapas.e09_metricas import digest
from pipeline.etapas.e09_metricas.classificacao_owasp import aplicar
from pipeline.etapas.e09_metricas.calculo import calcular
from pipeline.etapas.e09_metricas.publicacao import construir


class ClassificacaoTests(unittest.TestCase):
    def preparar(self, pasta, original=None, categoria='A05', duplicada=False):
        c = case()
        c['owasp_2025'] = original
        entrada = context(pasta, [row(c)], [c])
        save(entrada.catalogo.caminho, [c])
        config = pasta / 'classificacao'
        config.mkdir()
        tabela = config / 'classificacao-78-casos.csv'
        r = {'caso_id': c['caso_id'], 'owasp_2025_original': original or '',
             'owasp_2025_analise': categoria, 'classificacao_auditoria': 'falso_positivo',
             'metodo': 'categoria original preservada' if original else 'correspondência explícita CWE–OWASP',
             'justificativa': 'CWE-89 na lista A05.'}
        with tabela.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(r))
            writer.writeheader()
            writer.writerows([r, r] if duplicada else [r])
        save(config/'manifesto.json', {'schema_versao': '1.0', 'casos': 1,
             'catalogo_sha256': digest(entrada.catalogo.caminho), 'limite': 'fixture',
             'arquivos_sha256': {tabela.name: digest(tabela)}})
        return entrada, config

    def test_muda_grupo_sem_mudar_resultados_ou_fontes(self):
        with tempfile.TemporaryDirectory() as tmp:
            entrada, config = self.preparar(Path(tmp))
            brutas = copy.deepcopy(entrada.linhas)
            catalogo = copy.deepcopy(entrada.catalogo.casos)
            antes = calcular(entrada)
            aplicar(entrada, config)
            depois = calcular(entrada)
            for campo in ('populacoes', 'casos', 'metricas_por_caso', 'custos_tempos', 'cobertura'):
                self.assertEqual(antes[campo], depois[campo])
            self.assertEqual(entrada.catalogo.casos, catalogo)
            self.assertEqual(entrada.linhas[0]['original'], brutas[0]['original'])
            self.assertEqual(depois['agregacoes']['real_desenho']['owasp'][0]['grupo'], 'A05')
            self.assertIsNone(depois['agregacoes']['real_desenho']['owasp_original'][0]['grupo'])
            artefatos = construir(depois, entrada)
            self.assertIn('metricas_por_owasp_original.csv', artefatos)
            self.assertIn(b'owasp_2025_original', artefatos['tentativas.csv'])
            self.assertIn(b'owasp_2025_original', artefatos['casos.csv'])
            # A classificação também acompanha casos solicitados ainda sem tentativas.
            entrada.linhas = []
            artefatos = construir(calcular(entrada), entrada)
            self.assertIn(b'A05', artefatos['casos.csv'])

    def test_recusa_reclassificar_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            entrada, config = self.preparar(Path(tmp), original='A01')
            with self.assertRaisesRegex(ValueError, 'original não autorizada'):
                aplicar(entrada, config)
            self.assertEqual(entrada.linhas[0]['owasp_2025'], 'A01')

    def test_recusa_duplicatas(self):
        with tempfile.TemporaryDirectory() as tmp:
            entrada, config = self.preparar(Path(tmp), duplicada=True)
            with self.assertRaisesRegex(ValueError, 'População'):
                aplicar(entrada, config)

    def test_recusa_tabela_alterada_e_catalogo_divergente(self):
        for alteracao in ('tabela', 'catalogo'):
            with self.subTest(alteracao=alteracao), tempfile.TemporaryDirectory() as tmp:
                entrada, config = self.preparar(Path(tmp))
                caminho = config/'classificacao-78-casos.csv' if alteracao == 'tabela' else entrada.catalogo.caminho
                caminho.write_text(caminho.read_text() + '\n')
                with self.assertRaises(ValueError):
                    aplicar(entrada, config)


if __name__ == '__main__':
    unittest.main()
