"""Painel testado com processos sintéticos, sem LLM, Semgrep ou testes do alvo."""
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from pipeline.painel.controle import Controle, resumo_tentativa
from pipeline.painel.servidor import handler
from pipeline.orquestracao.campanha import parada_solicitada, processar_caso


class PainelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        self.config = {'modo': 'real', 'casos': ['AMP1'], 'estrategias': ['P1'], 'k': 1,
                       'saida_base': self.raiz / 'outputs/execucoes'}
        self.controle = Controle(self.raiz, self.raiz / 'config.yaml')
        self.addCleanup(self.controle.encerrar)
        config_patch = patch.object(self.controle, 'configuracao', return_value=self.config.copy())
        config_patch.start()
        self.addCleanup(config_patch.stop)

    def aguardar(self, condicao):
        limite = time.monotonic() + 5
        while not condicao():
            if time.monotonic() > limite:
                self.fail('Processo sintético não respondeu no prazo')
            time.sleep(.01)

    def test_tempos_medidos_e_estimativa_historica(self):
        linha = {'duracao_llm_s': 2, 'duracao_sast_s': 3, 'duracao_validacao_s': 5}
        antes = dict(linha)
        self.assertEqual(resumo_tentativa(linha)['tempos']['total'], 10)
        self.assertTrue(resumo_tentativa(linha)['total_estimado'])
        self.assertEqual(linha, antes)
        linha['duracao_total_s'] = 12
        self.assertEqual(resumo_tentativa(linha)['tempos']['total'], 12)
        self.assertFalse(resumo_tentativa(linha)['total_estimado'])
        linha.pop('duracao_sast_s')
        linha.pop('duracao_total_s')
        self.assertIsNone(resumo_tentativa(linha)['tempos']['total'])

    def test_cache_validacao_separado_do_llm_e_do_tempo_original(self):
        linha = {'do_cache': False, 'duracao_llm_s': 2, 'duracao_sast_s': 1,
                 'duracao_validacao_s': 3, 'politica_validacao': 'otimizada_v1',
                 'cache_validacao': {'sast': {'hit': True, 'duracao_original_s': 90}},
                 'etapas_validacao': [{'etapa': 'T0', 'status': 'executada'}]}
        resumo = resumo_tentativa(linha)
        self.assertFalse(resumo['cache'])
        self.assertTrue(resumo['cache_validacao']['sast']['hit'])
        self.assertEqual(resumo['tempos']['total'], 6)
        self.assertEqual(resumo['politica_validacao'], 'otimizada_v1')
        self.assertEqual(resumo['etapas_validacao'], linha['etapas_validacao'])

    def test_leitura_historica_parcial_e_escapes(self):
        pasta = self.raiz / 'outputs/execucao'
        arquivo = pasta / 'resultados_consolidados/execucoes.jsonl'
        arquivo.parent.mkdir(parents=True)
        arquivo.write_text(json.dumps({'caso_id': 'AMP1', 'estrategia_prompt': 'P3'}) + '\n{"parcial":', encoding='utf-8')
        linhas, avisos = self.controle.tentativas(pasta)
        self.assertEqual(len(linhas), 1)
        self.assertEqual(len(avisos), 1)
        with self.assertRaises(ValueError):
            self.controle.snapshot('../../.env')
        (self.raiz / 'outputs/atalho').symlink_to(self.raiz)
        with self.assertRaises(ValueError):
            self.controle.snapshot('atalho')

    def test_parada_cooperativa_nao_inicia_metricas_nem_segunda_execucao(self):
        pronta = self.raiz / 'pronta'
        restaurada = self.raiz / 'restaurada'
        metricas = self.raiz / 'metricas'
        script = ('import pathlib,sys,time; '
                  f'pathlib.Path({str(pronta)!r}).touch(); '
                  'p=pathlib.Path(sys.argv[-1]); '
                  '\nwhile not p.exists(): time.sleep(.01)\n'
                  f'pathlib.Path({str(restaurada)!r}).touch()')
        comandos = ([sys.executable, '-c', script],
                    [sys.executable, '-c', f'open({str(metricas)!r}, "w").close()'])
        with patch('pipeline.painel.controle.montar_comandos', return_value=comandos):
            self.controle.iniciar('dry-run')
            self.aguardar(pronta.exists)
            with self.assertRaises(ValueError):
                self.controle.iniciar('real')
            self.controle.parar()
            self.aguardar(lambda: not self.controle.worker.is_alive())
        self.assertTrue(restaurada.exists())
        self.assertFalse(metricas.exists())
        self.assertEqual(self.controle.atual['status'], 'interrompida')

    def test_finaliza_e_consolida_ou_reporta_falha(self):
        for codigo in (0, 3):
            with self.subTest(codigo=codigo):
                metricas = self.raiz / f'metricas{codigo}'
                comandos = ([sys.executable, '-c', f'raise SystemExit({codigo})'],
                            [sys.executable, '-c', f'open({str(metricas)!r}, "w").close()'])
                with patch('pipeline.painel.controle.montar_comandos', return_value=comandos):
                    self.controle.iniciar('preflight')
                    self.aguardar(lambda: not self.controle.worker.is_alive())
                self.assertEqual(metricas.exists(), codigo == 0)
                self.assertEqual(self.controle.atual['status'], 'finalizada' if codigo == 0 else 'falhou')

    def test_parada_do_orquestrador_devolve_worktree_sem_tentar_patch(self):
        from types import SimpleNamespace
        stop = self.raiz / 'parar'
        stop.touch()
        args = SimpleNamespace(arquivo_parada=stop, estrategias=['P1'], diagnosticos=[], execucao='E')
        ctx = SimpleNamespace(args=args, parar=threading.Event())
        eventos = []
        class Pool:
            @contextmanager
            def alugar(self):
                try:
                    yield Path('/tmp')
                finally:
                    eventos.append('restaurada')
        with patch('pipeline.orquestracao.campanha.nome_tentativa', return_value='T'), patch('pipeline.orquestracao.campanha.tentativa') as tentativa:
            processar_caso(ctx, Pool(), {'caso_id': 'AMP1'}, {})
        tentativa.assert_not_called()
        self.assertEqual(eventos, ['restaurada'])
        self.assertTrue(parada_solicitada(args))
        self.assertFalse(parada_solicitada(SimpleNamespace()))

    def test_novos_registros_recebem_total_medido(self):
        from types import SimpleNamespace
        args = SimpleNamespace(estrategias=['P1'], diagnosticos=[], execucao='E')
        ctx = SimpleNamespace(args=args, parar=threading.Event(), erros=[],
                              saidas=SimpleNamespace(execucoes=self.raiz / 'registro.jsonl'),
                              somar_custo=lambda valor: valor)
        linha = {'do_cache': False, 'custo_usd': 0, 'classificacao_final': 'rejeitada',
                 'status_aplicacao': 'aplicado', 'tier_falha': None, 'novas_issues_qtd': 0}
        class Pool:
            @contextmanager
            def alugar(self):
                yield Path('/tmp')
        with patch('pipeline.orquestracao.campanha.nome_tentativa', return_value='T'), \
                patch('pipeline.orquestracao.campanha.tentativa', return_value=linha), \
                patch('pipeline.orquestracao.campanha.registrar_execucao') as registrar, \
                patch('pipeline.orquestracao.campanha.console'):
            processar_caso(ctx, Pool(), {'caso_id': 'AMP1'}, {})
        registro = registrar.call_args.args[0]
        self.assertGreaterEqual(registro['duracao_total_s'], 0)
        self.assertIn('+00:00', registro['inicio_tentativa'])
        self.assertIn('+00:00', registro['fim_tentativa'])

    def test_api_exige_token_e_origem_e_nao_executa_ao_consultar(self):
        servidor = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.controle, 'segredo'))
        thread = threading.Thread(target=servidor.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection('127.0.0.1', servidor.server_port, timeout=3)
            conn.request('GET', '/api/status')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertFalse(json.loads(response.read())['ativo'])
            for headers in ({}, {'X-Painel-Token': 'segredo', 'Origin': 'http://outro-site'}):
                conn.request('POST', '/api/iniciar', json.dumps({'modo': 'real'}), headers)
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
            with patch.object(self.controle, 'iniciar', return_value='TESTE') as iniciar:
                conn.request('POST', '/api/iniciar', json.dumps({'modo': 'preflight'}), {'X-Painel-Token': 'segredo'})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                iniciar.assert_called_once_with('preflight')
            self.assertIsNone(self.controle.worker)
            conn.close()
        finally:
            servidor.shutdown()
            servidor.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
