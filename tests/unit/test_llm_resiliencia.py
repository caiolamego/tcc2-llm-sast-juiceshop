"""Transporte e fila com HTTP sintético; não acessa .env, API ou Juice Shop."""
from contextlib import nullcontext
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(Path(__file__).parent)]
import httpx
import openai
from pipeline.etapas.e05_geracao_llm import cliente_openai as mod
from pipeline.etapas.e05_geracao_llm.erros import ErroOperacionalLLM, GeracaoCancelada, atraso
from pipeline.orquestracao.campanha import Contexto, Saidas, processar_caso


class OpenAIResilienciaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = mod.ConfigLLM('secret-test-only', 'gpt-4.1-mini', 42, 40, 10)
        self.sequence = []; self.posts = 0; self.usage = True; self.choices = True
        self.http = httpx.Client(transport=httpx.MockTransport(self.handler))
        self.addCleanup(self.http.close)
        self.api = openai.OpenAI(api_key='secret-test-only', http_client=self.http, max_retries=0)
        self.addCleanup(self.api.close)
        self.client = mod.ClienteLLM.__new__(mod.ClienteLLM)
        self.client.cfg = self.cfg; self.client.parar = lambda: False; self.client._api = self.api
        self.client.orcamento = mod.Orcamento(40, 10, self.root/'budget.json')
        for patcher in (patch.object(mod, 'DIR_CACHE', self.root/'cache'), patch.object(mod, 'atraso', return_value=0)):
            patcher.start(); self.addCleanup(patcher.stop)

    def handler(self, req):
        self.posts += 1
        status = self.sequence.pop(0) if self.sequence else 200
        if status == 'timeout': raise httpx.ReadTimeout('secret-url', request=req)
        if status == 'connection': raise httpx.ConnectError('secret-url', request=req)
        if status != 200:
            return httpx.Response(429 if status == 'quota' else status,
                json={'error': {'message': 'secret-do-not-log', 'type': 'test',
                               'code': 'insufficient_quota' if status == 'quota' else 'test'}},
                headers={'Retry-After': '0'})
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 0,
            'model': self.cfg.modelo, 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': '{}', 'refusal': None}}] if self.choices else [],
            **({'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}} if self.usage else {})})

    def test_default_sem_cache_mesmo_com_entrada_corrompida(self):
        p = self.root/'cache'/f'{mod.hash_prompt([],self.cfg.modelo,42)}.json'
        p.parent.mkdir(); p.write_text('inválido')
        self.assertFalse(self.client.gerar([]).do_cache)
        self.assertFalse(self.client.gerar([]).do_cache)
        self.assertEqual(self.posts, 2); self.assertEqual(p.read_text(), 'inválido')
        self.assertEqual(json.loads((self.root/'budget.json').read_text())['chamadas'], 2)

    def test_cache_somente_quando_explicitamente_habilitado(self):
        self.client.cfg = replace(self.cfg, cache_llm='leitura-escrita')
        self.client.gerar([]); r = self.client.gerar([])
        self.assertTrue(r.do_cache); self.assertEqual(r.chamadas_enviadas, 0); self.assertEqual(self.posts, 1)

    def test_erros_transitorios_recuperam_sem_reutilizar_resposta(self):
        for status in ('timeout', 'connection', 408, 409, 429, 500, 502, 503):
            with self.subTest(status=status):
                before = self.posts; self.sequence = [status, 200]
                r = self.client.gerar([])
                self.assertEqual(self.posts-before, 2); self.assertEqual(r.chamadas_enviadas, 2)
                self.assertEqual(len(r.historico_transporte), 1); self.assertFalse(r.do_cache)
                self.assertNotIn('secret', str(r.historico_transporte))

    def test_esgotamento_registra_tres_envios_e_permite_proximo_prompt(self):
        self.sequence = ['timeout'] * 3
        with self.assertRaises(ErroOperacionalLLM) as caught: self.client.gerar([])
        e = caught.exception
        self.assertFalse(e.fatal); self.assertEqual(e.envios, 3)
        self.assertEqual(e.categoria, 'timeout'); self.assertEqual(len(e.historico), 3)
        self.assertNotIn('secret', str(e)); self.assertIsNone(e.metadados()['custo_usd'])
        self.assertFalse(self.client.gerar([{'role':'user','content':'outro'}]).do_cache)
        self.assertEqual(self.posts, 4)

    def test_autenticacao_cota_nao_repetem_e_sao_fatais(self):
        for status in (401, 403, 'quota'):
            with self.subTest(status=status):
                before = self.posts; self.sequence = [status]
                with self.assertRaises(ErroOperacionalLLM) as caught: self.client.gerar([])
                self.assertTrue(caught.exception.fatal); self.assertEqual(self.posts-before, 1)
                self.assertNotIn('secret', str(caught.exception))

    def test_requisicao_invalida_nao_repete_nem_bloqueia_outros_prompts(self):
        self.sequence = [400]
        with self.assertRaises(ErroOperacionalLLM) as caught: self.client.gerar([])
        self.assertFalse(caught.exception.fatal); self.assertEqual(self.posts, 1)

    def test_limite_conta_tambem_envios_que_falharam(self):
        self.client.orcamento.max_chamadas = 2; self.sequence = ['timeout'] * 3
        with self.assertRaises(mod.OrcamentoEsgotado): self.client.gerar([])
        self.assertEqual(self.posts, 2)
        self.assertEqual(json.loads((self.root/'budget.json').read_text())['chamadas'], 2)

    def test_tokens_ausentes_e_resposta_sem_choices(self):
        self.usage = False; r = self.client.gerar([])
        self.assertIsNone(r.tokens_entrada); self.assertIsNone(r.custo_usd)
        self.choices = False
        with self.assertRaises(ErroOperacionalLLM) as caught: self.client.gerar([])
        self.assertEqual(caught.exception.categoria, 'resposta_invalida')

    def test_cancelamento_sem_envio(self):
        self.client.parar = lambda: True
        with self.assertRaises(GeracaoCancelada): self.client.gerar([])
        self.assertEqual(self.posts, 0)

    def test_retry_after_limitado_e_fallback(self):
        for value, expected in [('12', 12), ('9999', 60), ('nan', 4), ('-1', 4), ('invalid', 4)]:
            exc = SimpleNamespace(response=httpx.Response(429, headers={'Retry-After': value}))
            self.assertEqual(atraso(exc, 2), expected)


class FilaResilienciaTests(unittest.TestCase):
    def test_falha_persistente_nao_bloqueia_proximos_prompts_e_casos(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ctx = Contexto(SimpleNamespace(dry_run=True, execucao='TEST', estrategias=['P1','P2'],
                                          diagnosticos=[], arquivo_parada=None), Saidas(root), None)
            ctx.ampliado = SimpleNamespace(catalogo=SimpleNamespace(commit='a'*40))
            pool = SimpleNamespace(alugar=lambda: nullcontext(root))
            failure = ErroOperacionalLLM('Timeout sintético', categoria='timeout', fatal=False, envios=3)
            with patch('pipeline.orquestracao.campanha.tentativa', side_effect=failure) as tentativa, \
                    patch('pipeline.orquestracao.campanha.registrar_execucao') as registrar, \
                    patch('pipeline.orquestracao.campanha.console'):
                for cid in ('AMP1', 'AMP2'):
                    processar_caso(ctx, pool, {'caso_id':cid,'owasp_2025':None,'sigla_vuln':'X'}, {})
            self.assertEqual(tentativa.call_count, 4); self.assertFalse(ctx.parar.is_set())
            registrar.assert_not_called(); self.assertTrue(ctx.custo_desconhecido)
            events = [json.loads(l) for l in (root/'llm_operacional.jsonl').read_text().splitlines()]
            self.assertEqual(len(events), 4)
            self.assertEqual({e['estrategia'] for e in events}, {'P1','P2'})
            self.assertEqual({e['caso_id'] for e in events}, {'AMP1','AMP2'})
            self.assertTrue(all(e['custo_usd'] is None for e in events))

    def test_recuperacao_proximo_prompt_registra_somente_resposta_recebida(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ctx = Contexto(SimpleNamespace(dry_run=True, execucao='TEST', estrategias=['P1','P2'],
                                          diagnosticos=[], arquivo_parada=None), Saidas(root), None)
            ctx.ampliado = SimpleNamespace(catalogo=SimpleNamespace(commit='a'*40))
            row = {'artefatos':{}, 'custo_usd':.1, 'do_cache':False,'classificacao_final':'nao_aplicada',
                   'status_aplicacao':'fixture','tier_falha':None,'novas_issues_qtd':None}
            with patch('pipeline.orquestracao.campanha.tentativa', side_effect=[
                    ErroOperacionalLLM('Timeout', categoria='timeout', fatal=False, envios=3), row]), \
                    patch('pipeline.orquestracao.campanha.registrar_execucao') as registrar, \
                    patch('pipeline.orquestracao.campanha.console'):
                processar_caso(ctx, SimpleNamespace(alugar=lambda:nullcontext(root)),
                    {'caso_id':'AMP1','owasp_2025':None,'sigla_vuln':'X'}, {})
            registrar.assert_called_once(); self.assertEqual(ctx.custo_sessao, .1)
            self.assertFalse(ctx.parar.is_set()); self.assertEqual(len(ctx.eventos_llm), 1)
