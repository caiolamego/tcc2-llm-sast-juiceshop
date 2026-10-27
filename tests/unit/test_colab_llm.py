"""Provedor Colab: somente HTTP local sintético, sem GPU, OpenAI ou alvo."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(Path(__file__).parent)]
import httpx
from pipeline.etapas.e05_geracao_llm.protocolo_colab import sha, validar_manifesto, read_json
from pipeline.etapas.e05_geracao_llm.provedor import (ConfigColab, ErroOperacionalLLM, GeracaoCancelada, provedor,
    identidade_offline, criar_cliente, texto_aplicavel, ambiente_alvo, resumo_publico)
from pipeline.etapas.e05_geracao_llm.cliente_colab import ClienteColab, Reservas, atomic_json, exclusive
from pipeline.etapas.e05_geracao_llm.cliente_openai import OrcamentoEsgotado
from pipeline.etapas.e05_geracao_llm.esquema import Correcao, response_format


def manifesto():
    scientific={'modelo':'Qwen/Qwen2.5-Coder-14B-Instruct','revisao':'a'*40,'tokenizer':'Qwen/Qwen2.5-Coder-14B-Instruct',
        'tokenizer_revisao':'a'*40,'chat_template_sha256':'b'*64,'servidor_sha256':'c'*64,
        'quantizacao':'bitsandbytes-nf4-double','dtype':'torch.float16','backend':'transformers-fastapi-lmformatenforcer',
        'versoes':{'transformers':'4.51.3','cuda':'12.4'}, 'contexto_tokens':8192,'saida_maxima_tokens':4096,
        'geracao':{'temperature':0,'do_sample':False,'stream':False},'capacidades':{'json_schema':True,'seed':True}}
    return {'schema_versao':'1.0','cientifica':scientific,'ambiente':{'gpu':'GPU sintética'},'identidade_sha256':sha(scientific)}


def correcao():
    return {'vulnerabilidade_identificada':'sintética','causa_da_vulnerabilidade':'fixture',
        'estrategia_de_correcao':'nenhuma','edicoes':[], 'justificativa_tecnica':'fixture','limitacoes_da_correcao':'fixture'}


class ColabTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.manifest=manifesto();self.mp=self.root/'manifest.json'
        atomic_json(self.mp,self.manifest)
        self.env=self.root/'test.env';self.write_env()
        self.clear=patch.dict('os.environ',{},clear=True);self.clear.start();self.addCleanup(self.clear.stop)
        self.cfg=ConfigColab.do_env(self.env)
        self.calls=[];self.sequence=[];self.posts=0
        self.finish='stop';self.content=json.dumps(correcao());self.usage=True;self.refusal=None
        self.remote=copy.deepcopy(self.manifest);self.model=self.cfg.modelo
        self.health_status=200

    def write_env(self, **overrides):
        values={'LLM_PROVIDER':'colab','COLAB_BASE_URL':'https://fixture.invalid/v1','COLAB_API_KEY':'test-private-token',
            'COLAB_MODEL':self.manifest['cientifica']['modelo'],'COLAB_MODEL_MANIFEST':str(self.mp)}
        values.update(overrides)
        self.env.write_text('\n'.join(f'{k}={v}' for k,v in values.items())+'\n')

    def handler(self, req):
        self.calls.append(req)
        if req.url.path=='/health':return httpx.Response(self.health_status,json={'status':'ok','manifest':self.remote})
        if req.url.path=='/v1/models':return httpx.Response(200,json={'data':[{'id':self.model}]})
        self.posts+=1
        body=json.loads(req.content)
        self.assertEqual(body['response_format'],response_format())
        self.assertEqual(body['temperature'],0);self.assertEqual(body['stream'],False)
        self.assertEqual(req.headers['X-LLM-Identity'],self.manifest['identidade_sha256'])
        self.assertEqual(req.headers['Authorization'],'Bearer test-private-token')
        status=self.sequence.pop(0) if self.sequence else 200
        if status=='timeout':raise httpx.ReadTimeout('sensitive-url',request=req)
        if status=='connection':raise httpx.ConnectError('sensitive-url',request=req)
        if status!=200:return httpx.Response(status,json={'error':{'message':'secret-not-for-logs','type':'test','code':status}},headers={'Retry-After':'0'})
        return httpx.Response(200,json={'id':'chat-test','object':'chat.completion','created':0,'model':self.model,
            'choices':[{'index':0,'finish_reason':self.finish,'message':{'role':'assistant','content':self.content,'refusal':self.refusal}}],
            **({'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}} if self.usage else {})})

    def client(self, cfg=None):
        http=httpx.Client(transport=httpx.MockTransport(self.handler));self.addCleanup(http.close)
        return ClienteColab(cfg or self.cfg,raiz_cache=self.root/'cache',http_client=http)

    def test_env_colab_sem_chave_openai_e_defaults(self):
        self.assertEqual(provedor(self.env),'colab');self.assertEqual(self.cfg.timeout,600)
        self.assertEqual(self.cfg.max_in_flight,1);self.assertEqual(self.cfg.max_tokens,4096)
        self.assertNotIn('test-private-token',repr(self.cfg))
        self.assertNotIn('fixture.invalid',str(self.cfg.identidade()))
        with patch('os.environ',{'COLAB_TIMEOUT_S':'900'}):self.assertEqual(ConfigColab.do_env(self.env).timeout,900)

    def test_openai_padrao_e_fabrica_compatibilidade(self):
        self.env.write_text('OPENAI_API_KEY=test-key\nOPENAI_MODEL=gpt-4.1-mini\n')
        self.assertEqual(provedor(self.env),'openai')
        with patch('pipeline.etapas.e05_geracao_llm.cliente_openai.ClienteLLM') as cls:
            criar_cliente(self.env);self.assertEqual(cls.call_args.args[0].modelo,'gpt-4.1-mini')
        self.assertEqual(identidade_offline(self.env)['provedor'],'openai')

    def test_config_invalidos_e_precedencia(self):
        for key,value in [('COLAB_BASE_URL','http://host/v1'),('COLAB_BASE_URL','https://user:secret@host/v1'),
            ('COLAB_BASE_URL','https://host/v1?key=abc'),('COLAB_BASE_URL','https://host/'),
            ('COLAB_API_KEY','<preencher>'),('COLAB_MODEL','outro'),('COLAB_MAX_IN_FLIGHT','2'),
            ('COLAB_MAX_OUTPUT_TOKENS','0'),('COLAB_MAX_OUTPUT_TOKENS','5000'),('COLAB_TIMEOUT_S','nan'),('MAX_LLM_CALLS','0')]:
            with self.subTest(key=key,value=value):
                self.write_env(**{key:value})
                with self.assertRaises(ValueError):ConfigColab.do_env(self.env)
        self.write_env(LLM_PROVIDER='invalido')
        with self.assertRaises(ValueError):provedor(self.env)

    def test_manifesto_adulterado_incompleto_e_json_duplicado(self):
        for field in ['revisao','chat_template_sha256','servidor_sha256','quantizacao','capacidades']:
            broken=copy.deepcopy(self.manifest);broken['cientifica'].pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError):validar_manifesto(broken)
        broken=copy.deepcopy(self.manifest);broken['cientifica']['dtype']='outro'
        with self.assertRaises(ValueError):validar_manifesto(broken)
        self.mp.write_text('{"a":1,"a":2}')
        with self.assertRaises(ValueError):read_json(self.mp)

    def test_diagnostico_sem_geracao_e_identidade_remota(self):
        c=self.client();report=c.conferir_conexao()
        self.assertEqual(report['estado'],'identidade_verificada');self.assertEqual(self.posts,0)
        self.assertFalse((self.root/'cache/orcamento.json').exists())
        self.remote['cientifica']['revisao']='d'*40;self.remote['identidade_sha256']=sha(self.remote['cientifica'])
        with self.assertRaises(ErroOperacionalLLM):c.conferir_conexao()

    def test_autenticacao_e_modelo_ausente_sem_reserva(self):
        c=self.client();self.health_status=401
        with self.assertRaisesRegex(ErroOperacionalLLM,'401'):c.gerar([])
        self.health_status=200;self.model='outro'
        with self.assertRaises(ErroOperacionalLLM):c.gerar([])
        self.assertEqual(self.posts,0)

    def test_geracao_schema_tokens_custo_e_cache(self):
        c=self.client();r=c.gerar([{'role':'user','content':'fixture'}])
        self.assertEqual(r.estado_geracao,'completa');self.assertIsNone(r.custo_usd)
        self.assertEqual(r.tokens_entrada,20);self.assertEqual(r.tokens_saida,10)
        self.assertEqual(Correcao.model_validate_json(texto_aplicavel(r)).edicoes,[])
        r2=c.gerar([{'role':'user','content':'fixture'}])
        self.assertTrue(r2.do_cache);self.assertEqual(r2.chamadas_enviadas,0)
        self.assertEqual(r2.latencia_s,0);self.assertEqual(self.posts,1)
        data=read_json(self.root/'cache/orcamento.json');self.assertEqual(data['chamadas'],1)
        alltext=''.join(p.read_text() for p in (self.root/'cache').rglob('*.json'))
        self.assertNotIn('test-private-token',alltext);self.assertNotIn('fixture.invalid',alltext)

    def test_detalhe_http_so_expoe_causas_conhecidas(self):
        from pipeline.etapas.e05_geracao_llm.cliente_colab import detalhe_http_seguro
        r=httpx.Response(503,json={'detail':'VRAM insuficiente para esta configuração'})
        self.assertIn('CUDA out of memory',detalhe_http_seguro(r))
        r=httpx.Response(503,text='<html>ERR_NGROK_3004 secret-token</html>')
        self.assertEqual(detalhe_http_seguro(r),'túnel ngrok informou ERR_NGROK_3004')
        for r in [httpx.Response(503,json={'detail':'private-token'}),httpx.Response(503,text='private-token'),httpx.Response(503,json={'detail':{'secret':'private-token'}})]:
            self.assertNotIn('private-token',detalhe_http_seguro(r))
            self.assertIn('origem não identificada',detalhe_http_seguro(r))

    def test_tokens_ausentes_nao_viram_zero(self):
        self.usage=False;r=self.client().gerar([])
        self.assertIsNone(r.tokens_entrada);self.assertIsNone(r.tokens_saida)

    def test_truncamento_recusa_e_json_invalido_sem_cache(self):
        for reason,content,refusal in [('length',json.dumps(correcao()),None),('stop','{',None),('stop',None,'não')]:
            self.finish,self.content,self.refusal=reason,content,refusal
            r=self.client().gerar([{'role':'user','content':str(reason)+str(content)}])
            self.assertNotEqual(r.estado_geracao,'completa')
            if reason=='length' or refusal:self.assertIsNone(texto_aplicavel(r))
        self.assertEqual(len(list((self.root/'cache').glob('respostas/*.json'))),0)

    def test_429_reservas_e_limite(self):
        c=self.client();self.sequence=[429,429,200];r=c.gerar([])
        self.assertEqual(r.chamadas_enviadas,3)
        data=read_json(self.root/'cache/orcamento.json');self.assertEqual(data['chamadas'],3)
        self.assertEqual([e['estado'] for e in data['eventos']],['http_429_sem_geracao','http_429_sem_geracao','resposta_recebida'])
        self.sequence=[429]*3
        with self.assertRaises(ErroOperacionalLLM):c.gerar([{'role':'user','content':'outro'}])
        self.assertEqual(self.posts,6)

    def test_falhas_nao_repetem_e_mensagens_nao_vazam(self):
        c=self.client()
        for status in (400,401,409,422,500,503,'timeout','connection'):
            self.sequence=[status];before=self.posts
            with self.subTest(status=status),self.assertRaises(ErroOperacionalLLM) as caught:c.gerar([{'role':'user','content':str(status)}])
            self.assertEqual(self.posts,before+1)
            self.assertNotIn('secret',str(caught.exception));self.assertNotIn('sensitive-url',str(caught.exception))
        ledger=read_json(self.root/'cache/orcamento.json')
        self.assertEqual(ledger['eventos'][-1]['estado'],'falha_operacional_consumo_desconhecido')

    def test_reservas_limite_persistente_concorrencia(self):
        r=Reservas(self.root/'limits',3)
        def reserve(_):
            try:return r.reservar('id','endpoint')
            except OrcamentoEsgotado:return None
        with ThreadPoolExecutor(max_workers=8) as pool:result=list(pool.map(reserve,range(12)))
        self.assertEqual(sum(x is not None for x in result),3)
        self.assertEqual(read_json(r.path)['chamadas'],3)
        with self.assertRaises(OrcamentoEsgotado):Reservas(self.root/'limits',3).reservar('id','e')

    def test_cache_integridade_e_mudanca_cientifica(self):
        c=self.client();c.gerar([])
        p=next((self.root/'cache/respostas').glob('*.json'));data=read_json(p)
        data['resposta']['conteudo']='alterado';atomic_json(p,data)
        with self.assertRaisesRegex(ErroOperacionalLLM,'Cache'):c.gerar([])
        self.assertEqual(self.posts,1)
        p.unlink();self.remote['cientifica']['revisao']='e'*40;self.remote['identidade_sha256']=sha(self.remote['cientifica'])
        with self.assertRaises(ErroOperacionalLLM):c.gerar([])

    def test_reconexao_troca_url_preserva_identidade_e_cache(self):
        c=self.client();c.gerar([])
        new=self.client(replace(self.cfg,base_url='https://novo.invalid/v1'))
        self.assertEqual(c.identidade,new.identidade)
        self.assertTrue(new.gerar([]).do_cache);self.assertNotEqual(c.endpoint,new.endpoint)

    def test_identidade_muda_com_revisao_seed_schema_e_timeout(self):
        original=self.cfg.identidade()
        self.assertNotEqual(original,replace(self.cfg,seed=43).identidade())
        self.assertNotEqual(original,replace(self.cfg,timeout=700).identidade())
        with patch('pipeline.etapas.e05_geracao_llm.provedor.response_format',return_value={'test':'schema'}):
            self.assertNotEqual(original,self.cfg.identidade())
        self.assertEqual(original,replace(self.cfg,api_key='new-token',base_url='https://new.invalid/v1').identidade())

    def test_cancelamento_na_fila_sem_reserva(self):
        c=self.client();c.parar=lambda:True
        with self.assertRaises(GeracaoCancelada):c.gerar([])
        self.assertEqual(self.posts,0)
        lock=self.root/'queue.lock'
        with exclusive(lock):
            stop=threading.Event()
            def queued():
                with exclusive(lock,stop.is_set):pass
            with ThreadPoolExecutor(1) as ex:
                f=ex.submit(queued);stop.set()
                with self.assertRaises(GeracaoCancelada):f.result(timeout=3)

    def test_dois_workers_patch_identico_geram_uma_vez(self):
        c=self.client()
        with ThreadPoolExecutor(2) as ex:rs=list(ex.map(lambda _:c.gerar([]),range(2)))
        self.assertEqual(self.posts,1);self.assertEqual(sum(r.do_cache for r in rs),1)

    def test_segredos_nao_repassados_ao_alvo(self):
        with patch.dict('os.environ',{'COLAB_API_KEY':'private','OPENAI_API_KEY':'private','NGROK_AUTHTOKEN':'private','PATH':'public'}):
            env=ambiente_alvo({'TZ':'UTC'})
            self.assertEqual(env,{'PATH':'public','TZ':'UTC'})

    def test_cli_help_fora_da_raiz_e_offline_sem_rede(self):
        cmd=[sys.executable,str(ROOT/'scripts/experimento/diagnosticar_llm.py')]
        result=subprocess.run(cmd+['--help'],cwd=self.root,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0);self.assertIn('offline',result.stdout)
        from scripts.experimento.diagnosticar_llm import main
        with patch('httpx.Client',side_effect=AssertionError('rede proibida')),patch('builtins.print'):
            self.assertEqual(main(['--modo','offline','--env',str(self.env)]),0)

    def test_diagnostico_openai_sem_chave_falha_offline(self):
        from scripts.experimento.diagnosticar_llm import main
        self.env.write_text('LLM_PROVIDER=openai\nOPENAI_API_KEY=<preencher>\n')
        with patch('httpx.Client',side_effect=AssertionError('rede proibida')),patch('builtins.print'):
            self.assertEqual(main(['--modo','offline','--env',str(self.env)]),1)

    def test_painel_sem_segredos_e_custo_desconhecido(self):
        from pipeline.painel.controle import resumo_tentativa
        info=resumo_publico(self.env);self.assertEqual(info['provedor'],'colab')
        self.assertNotIn('test-private-token',str(info));self.assertNotIn('fixture.invalid',str(info))
        r=resumo_tentativa({'provedor':'colab','modelo':'qwen','custo_usd':None,'espera_inferencia_s':2,'requisicao_s':4})
        self.assertIsNone(r['custo_usd']);self.assertEqual(r['espera_inferencia_s'],2)

    def test_notebook_sintaxe_sem_execucao_e_identidade(self):
        import ast
        data=json.loads((ROOT/'notebooks/qwen_colab_api.ipynb').read_text())
        source=''
        for cell in data['cells']:
            if cell['cell_type']!='code':continue
            self.assertFalse(cell.get('outputs'))
            s=''.join(cell['source'])
            if s.lstrip().startswith('%pip'):continue
            compile(s,'notebook','exec')
            tree=ast.parse(s)
            for node in tree.body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SERVER_SOURCE' for t in node.targets):
                    source=ast.literal_eval(node.value);compile(source,'server','exec')
        self.assertIn('x_llm_identity',source)
        self.assertIn('strict',source);self.assertNotIn('configure K=1',source)

    def test_http_local_real_compatibilidade_sdk(self):
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                payload={'status':'ok','manifest':outer.manifest} if self.path=='/health' else {'data':[{'id':outer.model}]}
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(payload).encode())
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.assertEqual(body['response_format'],response_format())
                outer.assertEqual(self.headers['X-LLM-Identity'],outer.manifest['identidade_sha256'])
                payload={'id':'local','object':'chat.completion','created':0,'model':outer.model,
                    'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(correcao())}}]}
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(payload).encode())
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            # Somente teste: configuração construída diretamente, sem relaxar validação HTTPS do .env.
            cfg=replace(self.cfg,base_url=f'http://127.0.0.1:{server.server_port}/v1')
            c=self.client(cfg);c.http.close()
            c=ClienteColab(cfg,raiz_cache=self.root/'http-cache')
            try:r=c.gerar([]);self.assertEqual(r.estado_geracao,'completa')
            finally:c.http.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':unittest.main()
