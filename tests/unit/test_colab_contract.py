"""Contratos novos, integrações e métricas sem geração ou execução do alvo."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(Path(__file__).parent)]
from test_colab_llm import manifesto, correcao
from test_validation_contract import entrada
from test_metrics import context, row, case
from pipeline.llm.provider import ConfigColab, identidade_offline
from pipeline.llm.colab_client import RespostaColab
from pipeline.execucao_ampliada import contrato_com_inferencia
from pipeline.metrics.loader import _validar_contrato
from pipeline.metrics.calculator import calcular
from pipeline.metrics.exporter import construir


class ColabContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest=manifesto()
        self.cfg=ConfigColab('https://test.invalid/v1','private',self.manifest['cientifica']['modelo'],self.manifest)
        self.identity=self.cfg.identidade()

    def test_nova_versao_valida_contexto_v3_e_preserva_objeto(self):
        entry=entrada();old=copy.deepcopy(entry.contrato)
        entry.contrato=contrato_com_inferencia(entry.contrato,self.identity)
        self.assertEqual(entry.contrato['schema_versao'],'5.0')
        self.assertEqual(entry.contrato['contrato_validacao_versao'],'3.0')
        with patch('pipeline.metrics.loader._perfil'):_validar_contrato(entry)
        self.assertEqual(old['schema_versao'],'3.0')

    def test_antigos_openai_sem_migracao_colab_recusado(self):
        for version in ('1.0','2.0','3.0','4.0'):
            previous={'schema_versao':version}
            current={'schema_versao':'3.0'}
            self.assertIs(contrato_com_inferencia(current,{'provedor':'openai'},previous),current)
            with self.assertRaisesRegex(ValueError,'nova execução'):
                contrato_com_inferencia(current,self.identity,previous)

    def test_retomada_mudanca_cientifica_diverge_url_nao_entra(self):
        old=contrato_com_inferencia(entrada().contrato,self.identity)
        current=contrato_com_inferencia(entrada().contrato,self.cfg.identidade(),old)
        self.assertEqual(old,current)
        for name in ('modelo','geracao','cientifica'):
            identity=copy.deepcopy(self.identity);identity[name]='modificado'
            self.assertNotEqual(old,contrato_com_inferencia(entrada().contrato,identity,old))
        self.assertNotIn('private',json.dumps(old));self.assertNotIn('test.invalid',json.dumps(old))

    def test_loader_recusa_identidade_ausente_e_adulterada(self):
        entry=entrada();entry.contrato=contrato_com_inferencia(entry.contrato,self.identity)
        for inf in (None, {'provedor':'invalido','modelo':'x'}, {**self.identity,'modelo_identidade_sha256':'0'*64}):
            broken=copy.deepcopy(entry);broken.contrato['inferencia']=inf
            with patch('pipeline.metrics.loader._perfil'),self.assertRaises(ValueError):_validar_contrato(broken)

    def test_v5_herda_cobertura_v4(self):
        # Exercita a validação do contexto sem executar baseline ou serviços.
        entry=entrada();entry.contrato=contrato_com_inferencia(entry.contrato,self.identity)
        entry.contrato['contrato_validacao_versao']='4.0'
        with patch('pipeline.metrics.loader._perfil'),self.assertRaises(ValueError):_validar_contrato(entry)

    def test_metricas_nulos_identidade_e_csv_deterministico(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=row(case('AMP_A'));a.update(provedor='colab',identidade_inferencia=self.identity,
                custo_usd=None,tokens_entrada=None,tokens_saida=None,custo_motivo='infraestrutura não medida')
            entry=context(Path(tmp),[a]);entry.contrato.update(schema_versao='5.0',contrato_validacao_versao='3.0',inferencia=self.identity)
            report=calcular(entry)
            general=report['populacoes']['real_desenho']
            self.assertEqual(general['tentativas'],1)
            cost=report['custos_tempos']['custo_usd']
            self.assertEqual(cost['ausentes'],1);self.assertEqual(cost['completude'],'parcial')
            self.assertEqual(report['custos_tempos']['custos_colab']['infraestrutura_usd']['ausentes'],1)
            self.assertEqual(len(report['agregacoes']['real_desenho']['inferencia']),1)
            artifacts=construir(report,entry)
            self.assertIn('metricas_por_inferencia.csv',artifacts)
            self.assertIn(b'identidade_inferencia',artifacts['tentativas.csv'])
            self.assertEqual(artifacts,construir(calcular(entry),entry))

    def test_contexto_pipeline_cria_provedor_e_confere_identidade(self):
        from pipeline.run_pipeline import Contexto
        cfg=SimpleNamespace(dry_run=False,llm_identidade=self.identity,arquivo_parada=None)
        with patch('pipeline.llm.provider.identidade_offline',return_value=self.identity),patch('pipeline.llm.provider.criar_cliente') as factory:
            ctx=Contexto(cfg,None,[],None)
            factory.assert_called_once();ctx.cliente.conferir_conexao.assert_called_once()
        with patch('pipeline.llm.provider.identidade_offline',return_value={'provedor':'outro'}),patch('pipeline.llm.provider.criar_cliente') as factory:
            with self.assertRaises(ValueError):Contexto(cfg,None,[],None)
            factory.assert_not_called()

    def test_contexto_dry_run_nao_cria_cliente_nem_conecta(self):
        from pipeline.run_pipeline import Contexto
        with patch('pipeline.llm.provider.criar_cliente',side_effect=AssertionError('rede')):
            ctx=Contexto(SimpleNamespace(dry_run=True),None,[],None)
        self.assertIsNone(ctx.cliente)

    def test_resposta_truncada_nao_altera_arquivo_nem_roda_validacao(self):
        from pipeline.run_pipeline import tentativa, Saidas
        from pipeline.prompts import builder
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'a.ts';file.write_text('original')
            args=SimpleNamespace(execucao='TEST',dry_run=False,llm_identidade=self.identity,estrategias=['P1'],diagnosticos=[])
            result=RespostaColab(json.dumps(correcao()),None,'length',self.cfg.modelo,None,42,1,1,1,'h',self.identity,0,1,1,{'gpu':'fake'},'endpoint','truncada_ou_incompleta')
            prompt=SimpleNamespace(mensagens=[],hash_prompt='h',estrategia='P1_simples',roteiro_status=None,roteiro_sha256=None,
                modo_contexto='arquivo_completo',to_dict=lambda:{},metadados_rag=lambda:{})
            issue={'caso_id':'AMP1','assinatura':'s','arquivo':'a.ts','linha_inicio':1,'check_id':'r','cwe':[],
                'owasp_2025':None,'sigla_vuln':'X'}
            from unittest.mock import Mock
            ctx=SimpleNamespace(versao_semgrep=None,args=args,saidas=Saidas(root/'out'),cliente=Mock(gerar=Mock(return_value=result)),ampliado=None)
            with patch('pipeline.run_pipeline.PoolWorktrees.restaurar'),patch.object(builder,'montar',return_value=prompt),patch('pipeline.run_pipeline.aplicar',side_effect=AssertionError('patch')),patch('pipeline.run_pipeline.validar',side_effect=AssertionError('testes')):
                line=tentativa(ctx,issue,'P1',root,'AMP1_P1')
            self.assertTrue(line['classificacao_final'].startswith('nao_aplicada'))
            self.assertEqual(file.read_text(),'original');self.assertIsNone(line['F']);self.assertIsNone(line['R'])
            self.assertIsNone(line['custo_usd'])


    def test_falha_operacional_interrompe_fila_sem_tentativa_concluida(self):
        from contextlib import nullcontext
        import threading
        from pipeline.run_pipeline import processar_caso
        from pipeline.llm.provider import ErroOperacionalLLM
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            args=SimpleNamespace(execucao='TEST',estrategias=['P1','P2'],diagnosticos=[],arquivo_parada=None)
            ctx=SimpleNamespace(args=args,parar=threading.Event(),erros=[],eventos_llm=[],
                lock_custo=threading.Lock(),saidas=SimpleNamespace(raiz=root))
            pool=SimpleNamespace(alugar=lambda:nullcontext(root))
            with patch('pipeline.run_pipeline.tentativa',side_effect=ErroOperacionalLLM('Colab indisponível')) as call,patch('pipeline.run_pipeline.registrar_execucao') as record:
                processar_caso(ctx,pool,{'caso_id':'AMP1','owasp_2025':None,'sigla_vuln':'X'}, {})
            self.assertTrue(ctx.parar.is_set());self.assertEqual(call.call_count,1)
            record.assert_not_called();self.assertEqual(len(ctx.eventos_llm),1)
            self.assertTrue((root/'llm_operacional.jsonl').is_file())

    def test_reservas_entre_processos_nao_ultrapassam_limite(self):
        with tempfile.TemporaryDirectory() as tmp:
            code="""from pathlib import Path
import sys
sys.path.insert(0,sys.argv[1])
from pipeline.llm.colab_client import Reservas
from pipeline.llm.openai_client import OrcamentoEsgotado
try: Reservas(Path(sys.argv[2]),1).reservar('identity','endpoint')
except OrcamentoEsgotado: sys.exit(4)
"""
            processes=[subprocess.Popen([sys.executable,'-c',code,str(ROOT/'src'),tmp],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(3)]
            results=[]
            for proc in processes:
                out,err=proc.communicate(timeout=15);results.append(proc.returncode)
            self.assertEqual(sorted(results),[0,4,4])
            self.assertEqual(json.loads((Path(tmp)/'orcamento.json').read_text())['chamadas'],1)

    def test_v5_cobertura_valida_e_exporta_agrupamento(self):
        entry=entrada();base=entry.contrato
        base.update(schema_versao='4.0',baseline_testes_sha256='d'*64)
        base['validacao'].update(politica_validacao='relacionada_v2',mapa_testes_sha256='b'*64,
            baseline_sha256='d'*64,cobertura={'mapa_sha256':'b'*64,'revisao_sha256':'c'*64,'conjunto_d_sha256':'e'*64})
        entry.contrato=contrato_com_inferencia(base,self.identity)
        with patch('pipeline.metrics.loader._perfil'),patch('pipeline.metrics.loader._cobertura') as cov:
            _validar_contrato(entry);cov.assert_called_once()
        with tempfile.TemporaryDirectory() as tmp:
            record=row();record.update(provedor='colab',identidade_inferencia=self.identity,custo_usd=None,
                cobertura_funcional='relacionada_v2',cobertura_detalhada={'dominios':['api'],'grupos_selecionados':['g'],'suficiente':True})
            ent=context(Path(tmp),[record]);ent.contrato.update(schema_versao='5.0',contrato_validacao_versao='4.0',inferencia=self.identity)
            report=calcular(ent);artifacts=construir(report,ent)
            self.assertIn('metricas_por_cobertura_funcional.csv',artifacts)
            self.assertIn('metricas_por_inferencia.csv',artifacts)

    def test_alteracao_manifesto_durante_uso_e_recusada(self):
        from pipeline.llm.colab_client import atomic_json, ClienteColab
        from pipeline.llm.provider import ErroOperacionalLLM
        from pipeline.llm.colab_protocol import sha
        import httpx
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'manifest.json';atomic_json(path,self.manifest)
            from dataclasses import replace
            cfg=replace(self.cfg,manifesto_path=path)
            client=ClienteColab(cfg,raiz_cache=root/'cache',http_client=httpx.Client(transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(AssertionError('rede')))))
            try:
                changed=copy.deepcopy(self.manifest);changed['cientifica']['dtype']='torch.bfloat16';changed['identidade_sha256']=sha(changed['cientifica']);atomic_json(path,changed)
                with self.assertRaises(ErroOperacionalLLM):client.gerar([])
                self.assertFalse((root/'cache/orcamento.json').exists())
            finally:client.http.close()


if __name__=='__main__':unittest.main()
