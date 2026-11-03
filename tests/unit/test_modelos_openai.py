"""Perfis, payloads e preços com SDK real e transporte HTTP inteiramente sintético."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]
import httpx
import openai
from pipeline.etapas.e05_geracao_llm import cliente_openai as mod
from pipeline.etapas.e05_geracao_llm.modelos import MODELOS_OPENAI, parametros_geracao
from pipeline.etapas.e05_geracao_llm.provedor import identidade_offline, criar_cliente, texto_aplicavel
from pipeline.etapas.e05_geracao_llm.erros import ErroOperacionalLLM


class ModelosOpenAITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.requests = []
        self.returned = None; self.details = {}; self.reasoning = None; self.finish = 'stop'
        self.file = self.root/'fixture.env'
        self.file.write_text('OPENAI_API_KEY=synthetic-private-key\nOPENAI_MODEL=gpt-4.1-mini\n')
        env = patch.dict('os.environ', {}, clear=True); env.start(); self.addCleanup(env.stop)
        cache = patch.object(mod, 'DIR_CACHE', self.root/'cache'); cache.start(); self.addCleanup(cache.stop)

    def handler(self, req):
        data = json.loads(req.content); self.requests.append(data)
        return httpx.Response(200, json={'id':'synthetic','object':'chat.completion','created':0,
            'model': self.returned or data['model'], 'choices':[{'index':0,'finish_reason':self.finish,
            'message':{'role':'assistant','content':'{}','refusal':None}}],
            'usage':{'prompt_tokens':1000,'completion_tokens':100,'total_tokens':1100,
                     'prompt_tokens_details':self.details,
                     'completion_tokens_details':{'reasoning_tokens':self.reasoning}}})

    def client(self, model):
        cfg = mod.ConfigLLM('synthetic-private-key', model, 42, 100, 10)
        http = httpx.Client(transport=httpx.MockTransport(self.handler)); self.addCleanup(http.close)
        sdk = openai.OpenAI(api_key=cfg.api_key, http_client=http, max_retries=0); self.addCleanup(sdk.close)
        with patch.object(mod.openai, 'OpenAI', return_value=sdk): client = mod.ClienteLLM(cfg)
        client.orcamento = mod.Orcamento(100, 10, self.root/(model+'-budget.json'))
        return client

    def test_tres_payloads_sdk_sem_seed_nos_luna(self):
        for model in MODELOS_OPENAI:
            with self.subTest(model=model):
                result = self.client(model).gerar([{'role':'user','content':'fixture'}])
                body = self.requests[-1]
                self.assertEqual(body['model'], model)
                self.assertEqual(body['temperature'], 0); self.assertEqual(body['max_completion_tokens'],4096)
                self.assertEqual(body['response_format']['type'],'json_schema')
                self.assertEqual(result.modelo_solicitado,model)
                self.assertEqual(result.parametros_geracao,parametros_geracao(model))
                if 'luna' in model:
                    self.assertEqual(body['reasoning_effort'],'none'); self.assertNotIn('seed',body)
                    self.assertIsNone(result.seed)
                else:
                    self.assertEqual(body['seed'],42); self.assertNotIn('reasoning_effort',body)
                    self.assertEqual(result.seed,42)
                self.assertFalse(result.do_cache)
                self.assertIsNone(result.tokens_raciocinio)

    def test_snapshot_da_familia_preserva_modelo_solicitado(self):
        self.returned = 'gpt-4.1-mini-2025-04-14'
        result = self.client('gpt-4.1-mini').gerar([])
        self.assertEqual(result.modelo,self.returned); self.assertEqual(result.modelo_solicitado,'gpt-4.1-mini')

    def test_resposta_de_outro_modelo_nao_pode_entrar_no_experimento(self):
        self.returned = 'gpt-4.1-mini'
        with self.assertRaises(ErroOperacionalLLM) as caught: self.client('gpt-6-luna').gerar([])
        self.assertEqual(caught.exception.categoria,'identidade_modelo'); self.assertTrue(caught.exception.fatal)
        self.assertEqual(len(self.requests),1)

    def test_registra_tokens_e_cobra_cache_leitura_e_escrita_sem_duplicar(self):
        self.details = {'cached_tokens':100,'cache_write_tokens':100}; self.reasoning = 0
        result = self.client('gpt-5.6-luna').gerar([])
        expected = (800*.2 + 100*.02 + 100*.25 + 100*1.2)/1_000_000
        self.assertEqual(result.custo_usd,round(expected,6))
        self.assertEqual(result.tokens_entrada_cache,100); self.assertEqual(result.tokens_escrita_cache,100)
        self.assertEqual(result.tokens_raciocinio,0)
        ledger = json.loads((self.root/'gpt-5.6-luna-budget.json').read_text())
        self.assertEqual(ledger['chamadas'],1); self.assertEqual(ledger['usd'],round(expected,6))

    def test_precos_dos_tres_modelos_e_contexto_longo(self):
        for model,pi,po in [('gpt-4.1-mini',.4,1.6),('gpt-5.6-luna',.2,1.2),('gpt-6-luna',.1,.5)]:
            with self.subTest(model=model):
                self.assertAlmostEqual(mod._custo(model,1000,0,100), (1000*pi+100*po)/1e6)
        self.assertAlmostEqual(mod._custo('gpt-6-luna',272001,0,100), (272001*.1*2+100*.5*1.5)/1e6)

    def test_contagem_de_cache_inconsistente_rejeitada(self):
        self.details = {'cached_tokens':900,'cache_write_tokens':200}
        with self.assertRaises(ErroOperacionalLLM) as caught: self.client('gpt-6-luna').gerar([])
        self.assertEqual(caught.exception.categoria,'resposta_invalida')

    def test_modelo_nao_cadastrado_falha_sem_criar_sdk(self):
        for model in ('gpt-6-luna-outra-coisa','nao-existe','gpt-5.6-sol'):
            with self.subTest(model=model), patch.object(mod.openai,'OpenAI') as sdk:
                with self.assertRaises(ValueError): self.client(model)
                sdk.assert_not_called()

    def test_selecao_explicita_supera_env_colab_sem_mudar_arquivo(self):
        self.file.write_text('LLM_PROVIDER=colab\nOPENAI_API_KEY=synthetic-private-key\nOPENAI_MODEL=nao-existe\n')
        original = self.file.read_bytes()
        identity = identidade_offline(self.file, modelo='gpt-6-luna')
        self.assertEqual(identity['provedor'],'openai'); self.assertEqual(identity['modelo'],'gpt-6-luna')
        self.assertEqual(identity['geracao']['reasoning_effort'],'none'); self.assertNotIn('seed',identity['geracao'])
        self.assertEqual(identity['precos']['saida'],.5)
        self.assertNotIn('synthetic-private-key',json.dumps(identity))
        with patch.object(mod,'ClienteLLM') as factory:
            criar_cliente(self.file, modelo='gpt-6-luna')
            self.assertEqual(factory.call_args.args[0].modelo,'gpt-6-luna')
        self.assertEqual(self.file.read_bytes(),original)

    def test_cache_nao_mistura_modelos_ou_parametros_efetivos(self):
        hashes = {mod.hash_prompt([],m,42) for m in MODELOS_OPENAI}; self.assertEqual(len(hashes),3)
        self.assertNotEqual(mod.hash_prompt([],'gpt-4.1-mini',42),mod.hash_prompt([],'gpt-4.1-mini',43))
        self.assertEqual(mod.hash_prompt([],'gpt-6-luna',42),mod.hash_prompt([],'gpt-6-luna',43))

    def test_preco_alterado_na_sessao_impede_novos_envios(self):
        table = self.root/'precos.yaml'; table.write_bytes(mod.ARQ_PRECOS.read_bytes())
        with patch.object(mod,'ARQ_PRECOS',table):
            client = self.client('gpt-6-luna')
            table.write_text(table.read_text()+'\n# alteração sintética\n')
            with self.assertRaises(ErroOperacionalLLM) as caught: client.gerar([])
            self.assertTrue(caught.exception.fatal); self.assertFalse(self.requests)

    def test_resposta_incompleta_e_recusa_nunca_sao_aplicaveis(self):
        self.finish = 'length'; result = self.client('gpt-6-luna').gerar([])
        self.assertIsNone(texto_aplicavel(result)); self.assertEqual(result.conteudo,'{}')
        self.assertIsNone(texto_aplicavel(replace(result,finish_reason='stop',recusa='recusa sintética')))

    def test_contrato_recusa_raciocinio_ativado_ou_seed_inventada(self):
        from copy import deepcopy
        from test_validation_contract import entrada
        from pipeline.orquestracao.preflight import contrato_com_inferencia
        from pipeline.etapas.e09_metricas.leitura import _validar_contrato
        entry = entrada()
        entry.contrato = contrato_com_inferencia(entry.contrato,identidade_offline(self.file,modelo='gpt-6-luna'))
        with patch('pipeline.etapas.e09_metricas.leitura._perfil'): _validar_contrato(entry)
        for key,value in [('reasoning_effort','medium'),('seed',42)]:
            broken = deepcopy(entry); broken.contrato['inferencia']['geracao'][key] = value
            with self.subTest(key=key), patch('pipeline.etapas.e09_metricas.leitura._perfil'), self.assertRaises(ValueError):
                _validar_contrato(broken)

    def test_resposta_sdk_ate_csv_com_proveniencia_e_recusa_de_troca(self):
        from test_metrics import expanded, save
        from test_validation_contract import entrada
        from pipeline.etapas.e09_metricas import digest
        from pipeline.etapas.e09_metricas.leitura import carregar
        from pipeline.etapas.e09_metricas.calculo import calcular
        from pipeline.etapas.e09_metricas.publicacao import construir
        inp,cat,case,row = expanded(self.root/'scenario')
        reply = self.client('gpt-6-luna').gerar([])
        identity = identidade_offline(self.file,modelo='gpt-6-luna')
        contract_path = inp/'contrato_execucao.json'
        contract = json.loads(contract_path.read_text())
        contract.update(schema_versao='5.0',contrato_validacao_versao='3.0',inferencia=identity,
                        validacao=entrada().contrato['validacao'])
        save(contract_path,contract)
        h = digest(contract_path)
        gate_path = inp/'sast_antes/reproducao.json'; gate = json.loads(gate_path.read_text())
        gate['contrato_execucao_sha256'] = h; save(gate_path,gate)
        row.update({k:v for k,v in reply.to_dict().items() if k!='conteudo'})
        row.update(provedor='openai',identidade_inferencia=identity,contrato_execucao_sha256=h,
                   status_aplicacao='sem_edicoes',classificacao_final='nao_aplicada:sem_edicoes',R=None,F=None,M=None)
        for d in ('criterio','marcador','sem_separacao'):
            row['F_'+d] = None; row['classificacao_'+d] = row['classificacao_final']
        rows_path = inp/'resultados_consolidados/execucoes.jsonl'
        rows_path.write_text(json.dumps(row)+'\n')
        loaded = carregar(inp,'TEST',cat); report = calcular(loaded); artifacts = construir(report,loaded)
        self.assertEqual(report['agregacoes']['real_desenho']['inferencia'][0]['grupo']['modelo'],'gpt-6-luna')
        self.assertIn(b'tokens_raciocinio',artifacts['tentativas.csv'])
        self.assertIn(b'reasoning_effort',artifacts['tentativas.csv'])
        row['modelo_solicitado'] = 'gpt-5.6-luna'; rows_path.write_text(json.dumps(row)+'\n')
        with self.assertRaisesRegex(ValueError,'divergem'): carregar(inp,'TEST',cat)
