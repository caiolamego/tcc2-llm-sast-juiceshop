"""Aplicação conservadora e atômica, sem LLM, Node ou testes do alvo."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from pipeline.etapas.e06_aplicacao import aplicador as a, indentacao as i
from pipeline.etapas.e05_geracao_llm.esquema import Correcao


def correction(*edits):
    return Correcao(vulnerabilidade_identificada='fixture',causa_da_vulnerabilidade='fixture',
        estrategia_de_correcao='fixture',edicoes=[{'arquivo':f,'trecho_original':old,'trecho_corrigido':new} for f,old,new in edits],
        justificativa_tecnica='fixture',limitacoes_da_correcao='fixture')


class ApplierTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.file=self.root/'route.ts';self.old='for (const x of xs) {\n  use(x)\n}';self.new='for (const x of xs) {\n  safe(x)\n}'
        self.source='function f() {\n    for (const x of xs) {\n      use(x)\n    }\n}\n';self.file.write_text(self.source)
    def apply(self,old=None,new=None,file='route.ts'):
        return a.aplicar(self.root,correction((file,self.old if old is None else old,self.new if new is None else new)))
    def test_exata_prioritaria_sem_parser(self):
        with patch.object(i,'tokens_equivalentes',side_effect=AssertionError('parser desnecessário')):
            r=self.apply('use(x)','safe(x)')
        self.assertEqual(r.status,'aplicado');self.assertEqual(r.correspondencias[0]['metodo'],'exata')
    @patch.object(i,'tokens_equivalentes',return_value=True)
    def test_indenta_bloco_e_preserva_entorno(self,_):
        r=self.apply();self.assertEqual(r.status,'aplicado')
        self.assertEqual(self.file.read_text(),self.source.replace('use(x)','safe(x)'))
        self.assertEqual(r.correspondencias[0]['metodo'],'indentacao_uniforme')
        self.assertEqual(r.correspondencias[0]['deslocamento'],['adicionar','    '])
    @patch.object(i,'tokens_equivalentes',return_value=True)
    def test_remove_prefixo_uniforme(self,_):
        self.file.write_text('for (const x of xs) {\n  use(x)\n}\n')
        r=self.apply('    '+self.old.replace('\n','\n    '),'    '+self.new.replace('\n','\n    '))
        self.assertEqual(r.status,'aplicado');self.assertEqual(self.file.read_text(),self.new+'\n')
    @patch.object(i,'tokens_equivalentes',return_value=True)
    def test_recuo_com_tabs(self,_):
        self.file.write_text('\tfor (const x of xs) {\n\t  use(x)\n\t}\n')
        r=self.apply();self.assertEqual(r.status,'aplicado');self.assertIn('\t  safe(x)',self.file.read_text())
    @patch.object(i,'tokens_equivalentes',return_value=True)
    def test_crlf_preservado(self,_):
        self.file.write_bytes(self.source.replace('\n','\r\n').encode())
        self.assertEqual(self.apply().status,'aplicado')
        data=self.file.read_bytes();self.assertEqual(data,self.source.replace('use(x)','safe(x)').replace('\n','\r\n').encode())
    @patch.object(i,'tokens_equivalentes',return_value=True)
    def test_novas_linhas_comentarios_e_remocao_bloco(self,_):
        self.assertEqual(self.apply(new='// intenção da LLM\n// segunda linha\n').status,'aplicado')
        self.assertIn('    // intenção da LLM\n    // segunda linha\n',self.file.read_text())
    @patch.object(i,'tokens_equivalentes',return_value=True)
    def test_ambiguidade_recuos_distintos_recusada(self,_):
        self.file.write_text(self.source+self.source.replace('    ','        '))
        before=self.file.read_bytes();r=self.apply()
        self.assertEqual(r.status,'ancora_ambigua');self.assertEqual(self.file.read_bytes(),before)
    def test_conteudo_string_nao_e_normalizado(self):
        self.file.write_text('    let x = "a  b"\n    use(x)\n')
        r=self.apply('let x = "a b"\nuse(x)','let x = "c"\nuse(x)')
        self.assertEqual(r.status,'ancora_nao_encontrada')
    def test_recuo_relativo_diferente_recusado(self):
        r=self.apply(self.old.replace('  use','    use'));self.assertEqual(r.status,'ancora_nao_encontrada')
    def test_deslocamento_nao_uniforme_inclusive_zero(self):
        real=i.linhas('    first()\n      second()');anchor=i.linhas('    first()\nsecond()')
        self.assertIsNone(i.deslocamento(anchor,real))
    @patch.object(i,'tokens_equivalentes',return_value=False)
    def test_template_ou_parser_inseguro_recusado(self,_):
        before=self.file.read_bytes();self.assertEqual(self.apply().status,'ancora_nao_encontrada');self.assertEqual(before,self.file.read_bytes())
    def test_tokens_de_literal_multilinha_precisam_ser_identicos(self):
        value={'antes':{'tokens':[{'texto':'`a\n  b`'}]},'depois':{'tokens':[{'texto':'`a\nb`'}]}}
        with patch.object(i.estrutura,'analisar',return_value=value):
            self.assertFalse(i.tokens_equivalentes('a.ts','old','new',self.root))
    def test_parser_ausente_recusa_fallback(self):
        self.assertFalse(i.tokens_equivalentes('a.ts','a','b',self.root))
    @patch.object(i,'tokens_equivalentes',side_effect=[True,False])
    def test_protecao_tambem_da_solucao_proposta(self,_):
        before=self.file.read_bytes();r=self.apply();self.assertEqual(r.status,'ancora_nao_encontrada')
        self.assertIn('correcao_insegura',r.detalhe);self.assertEqual(before,self.file.read_bytes())
    @patch.object(i,'tokens_equivalentes',return_value=True)
    def test_edicoes_acumulam_no_mesmo_arquivo(self,_):
        c=correction(('route.ts',self.old,self.new),('route.ts','safe(x)','safer(x)'))
        r=a.aplicar(self.root,c);self.assertEqual(r.status,'aplicado');self.assertIn('safer(x)',self.file.read_text());self.assertEqual(len(r.correspondencias),2)
    @patch.object(i,'tokens_equivalentes',return_value=True)
    def test_segunda_edicao_invalida_nao_escreve_primeira(self,_):
        before=self.file.read_bytes();r=a.aplicar(self.root,correction(('route.ts',self.old,self.new),('route.ts','ausente','nada')))
        self.assertEqual(r.status,'ancora_nao_encontrada');self.assertEqual(before,self.file.read_bytes())
    def test_outros_dominios_continuam_exatos(self):
        self.file.rename(self.root/'route.py');r=self.apply(file='route.py');self.assertEqual(r.status,'ancora_nao_encontrada')
    def test_caminho_externo_recusado(self):
        self.assertEqual(self.apply(file='../route.ts').status,'fora_de_escopo')

if __name__=='__main__':unittest.main()
