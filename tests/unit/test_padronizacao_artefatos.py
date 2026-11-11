"""Renomeação documental preserva payloads e mantém referências verificáveis."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from tests.unit.test_metrics import save
from scripts.relatorios import padronizar_artefatos_finais as p

CASO = 'AMP0123456789abcdef'
ANTIGO = CASO + '_SEMOWASP_OUTRO_P1_EXEC'
NOVO = CASO + '_A05_OUTRO_P1_EXEC'


class PadronizacaoTests(unittest.TestCase):
    def test_prefixo_muda_categoria_preservando_demais_campos(self):
        self.assertEqual(p.nome_revisado(ANTIGO+'_raw.json', {CASO: 'A05'}), NOVO+'_raw.json')
        self.assertEqual(p.nome_revisado(NOVO, {CASO: 'A05'}), NOVO)
        with self.assertRaises(ValueError):
            p.nome_revisado(ANTIGO, {})

    def test_recusa_colisao_antes_de_copiar(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            origem = raiz/'origem'
            origem.mkdir()
            (origem/(ANTIGO+'.json')).write_text('a')
            (origem/(NOVO+'.json')).write_text('b')
            with patch.object(p, 'RAIZ_REPO', raiz), self.assertRaisesRegex(ValueError, 'Colisão'):
                p.copiar_arvore(origem, raiz/'destino', {CASO: 'A05'}, set())
            self.assertFalse((raiz/'destino').exists())

    def test_copias_preservam_conteudo_e_atualizam_indices(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            fonte = raiz/'outputs/campanha_docker/EXEC'
            corpo = b'{"mensagens":[{"content":"codigo original"}]}\n'
            arquivo = fonte/'prompts'/(ANTIGO+'.json')
            arquivo.parent.mkdir(parents=True)
            arquivo.write_bytes(corpo)
            h = hashlib.sha256(corpo).hexdigest()
            relativo = 'prompts/'+ANTIGO+'.json'
            linha = {'caso_id': CASO, 'tentativa_id': ANTIGO, 'owasp_2025': None,
                     'R': None, 'F': 0, 'M': 1,
                     'artefatos_sha256': {relativo: h},
                     'artefatos': {'prompt': 'outputs/campanha_docker/EXEC/'+relativo}}
            registros = fonte/'resultados_consolidados/execucoes.jsonl'
            registros.parent.mkdir()
            registros.write_text(json.dumps(linha)+'\n')
            save(fonte/'resultados_consolidados/EXEC_sessoes.json', [{'saida': str(fonte)}])
            save(raiz/'outputs/rris/EXEC/manifesto.json', {'ordem_aplicacao': [ANTIGO]})
            antes = {f: f.read_bytes() for f in raiz.rglob('*') if f.is_file()}
            destino = raiz/'outputs/resultados_finais/V2/EXEC'
            with patch.object(p, 'RAIZ_REPO', raiz):
                campanha, rris, mapa, ids = p.preparar_campanha('EXEC', destino, {CASO: 'A05'})
            self.assertEqual(ids, {ANTIGO: NOVO})
            self.assertEqual((campanha/'prompts'/(NOVO+'.json')).read_bytes(), corpo)
            nova = json.loads((campanha/'resultados_consolidados/execucoes.jsonl').read_text())
            self.assertEqual(nova['tentativa_id_original'], ANTIGO)
            self.assertEqual(nova['owasp_2025'], 'A05')
            self.assertIsNone(nova['owasp_2025_original'])
            self.assertEqual((nova['R'], nova['F'], nova['M']), (None, 0, 1))
            self.assertEqual(list(nova['artefatos_sha256']), ['prompts/'+NOVO+'.json'])
            self.assertTrue((raiz/nova['artefatos']['prompt']).is_file())
            self.assertEqual(json.loads((rris/'manifesto.json').read_text())['ordem_aplicacao'], [NOVO])
            self.assertTrue(all(f.read_bytes() == b for f, b in antes.items()))
            self.assertTrue(all(x['sha256_original'] == x['sha256_atual'] for x in mapa if not x['indice_reescrito']))


if __name__ == '__main__':
    unittest.main()
