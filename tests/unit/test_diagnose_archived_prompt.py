"""Envio isolado de prompt arquivado, com cliente inteiramente simulado."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from scripts.experiment.diagnose_llm import main,ler_prompt
from pipeline.llm.provider import ErroOperacionalLLM


class ArchivedPromptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'prompt.json';self.out=self.root/'novo'
        self.messages=[{'role':'system','content':'instruções originais'},{'role':'user','content':'código original'}]
        data={'mensagens':self.messages,'hash_prompt':hashlib.sha256(json.dumps(self.messages,ensure_ascii=False).encode()).hexdigest()}
        self.path.write_text(json.dumps(data,sort_keys=True,ensure_ascii=False))
        self.raw=self.path.read_bytes()
        reply={'vulnerabilidade_identificada':'fixture','causa_da_vulnerabilidade':'fixture',
               'estrategia_de_correcao':'fixture','edicoes':[], 'justificativa_tecnica':'fixture','limitacoes_da_correcao':'fixture'}
        result={'conteudo':json.dumps(reply),'chamadas_enviadas':1,'do_cache':False,'latencia_s':1.5,'finish_reason':'stop'}
        self.response=SimpleNamespace(**result,to_dict=lambda:result)
        self.client=Mock();self.client.gerar.return_value=self.response;self.client.conferir_conexao.return_value={'estado':'identidade_verificada'}
        self.patches=[patch('scripts.experiment.diagnose_llm.identidade_offline',return_value={'provedor':'colab','modelo':'fixture'}),
            patch('scripts.experiment.diagnose_llm.criar_cliente',return_value=self.client),patch('builtins.print')]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def args(self):return ['--modo','prompt','--prompt-arquivo',str(self.path),'--saida',str(self.out)]

    def test_envia_mensagens_exatas_preserva_arquivo_e_salva_resposta(self):
        self.assertEqual(main(self.args()),0)
        self.client.gerar.assert_called_once_with(self.messages)
        self.assertEqual(self.path.read_bytes(),self.raw)
        self.assertEqual((self.out/'prompt.json').read_bytes(),self.raw)
        result=json.loads((self.out/'resultado.json').read_text())
        self.assertFalse(result['aplica_patch']);self.assertFalse(result['executa_sast']);self.assertFalse(result['executa_testes'])
        self.assertEqual(result['geracoes'],1);self.assertTrue((self.out/'resposta.json').is_file())

    def test_erro_operacional_publico_arquivado_sem_nova_tentativa(self):
        self.client.gerar.side_effect=ErroOperacionalLLM('HTTP 503: VRAM insuficiente')
        self.assertEqual(main(self.args()),1)
        result=json.loads((self.out/'resultado.json').read_text())
        self.assertIn('VRAM',result['erro']);self.assertIsNone(result['geracoes'])
        self.assertFalse((self.out/'resposta.json').exists());self.assertEqual(self.path.read_bytes(),self.raw)
        self.client.gerar.assert_called_once()

    def test_destino_existente_nunca_alterado(self):
        self.out.mkdir();previous=self.out/'resultado.json';previous.write_text('historico')
        self.assertEqual(main(self.args()),1)
        self.assertEqual(previous.read_text(),'historico');self.client.gerar.assert_not_called()
        self.client.conferir_conexao.assert_not_called()

    def test_hash_adulterado_recusado_antes_da_rede(self):
        d=json.loads(self.path.read_text());d['mensagens'][0]['content']='alterado';self.path.write_text(json.dumps(d))
        self.assertEqual(main(self.args()),1)
        self.assertFalse(self.out.exists());self.client.conferir_conexao.assert_not_called()

    def test_mensagem_teste_enviada_pelo_cliente_comum(self):
        self.assertEqual(main(['--modo','mensagem','--mensagem','teste','--saida',str(self.out)]),0)
        self.client.gerar.assert_called_once_with([{'role':'user','content':'teste'}])
        result=json.loads((self.out/'resultado.json').read_text())
        self.assertEqual(result['tipo'],'diagnostico_mensagem_livre')
        self.assertFalse(result['aplica_patch']);self.assertFalse(result['executa_sast'])
        raw,messages,h=ler_prompt(self.out/'prompt.json')
        self.assertEqual(messages,[{'role':'user','content':'teste'}])

    def test_mensagem_padrao_e_vazia(self):
        self.assertEqual(main(['--modo','mensagem','--saida',str(self.out)]),0)
        self.client.gerar.assert_called_once_with([{'role':'user','content':'teste'}])
        with self.assertRaises(SystemExit) as ex:main(['--modo','mensagem','--mensagem','   '])
        self.assertEqual(ex.exception.code,2)

    def test_parametro_obrigatorio(self):
        with self.assertRaises(SystemExit) as ex:main(['--modo','prompt'])
        self.assertEqual(ex.exception.code,2)


if __name__=='__main__':unittest.main()
