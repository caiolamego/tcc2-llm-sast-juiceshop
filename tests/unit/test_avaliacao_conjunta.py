"""Lógica da avaliação conjunta e da comparação entre modelos, sem Docker nem LLM."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT)]
import importlib.util
import subprocess
import tempfile
import unittest


def carregar(nome, caminho):
    spec=importlib.util.spec_from_file_location(nome,ROOT/caminho)
    modulo=importlib.util.module_from_spec(spec);spec.loader.exec_module(modulo)
    return modulo


conjunta=carregar('avaliacao_conjunta_rris','scripts/experimento/avaliacao_conjunta_rris.py')
comparar=carregar('comparar_modelos','scripts/relatorios/comparar_modelos.py')


def linha(tid, inicio, **campos):
    base={'tentativa_id':tid,'condicao':'desenho','dry_run':False,'pos_aceite':False,'status_aplicacao':'aplicado',
          'R':1,'F_criterio':1,'M':1,'original':{'inicio_tentativa':inicio}}
    return {**base,**campos}


class SelecaoTests(unittest.TestCase):
    def test_mantem_so_o_primeiro_aceite_do_desenho_em_ordem(self):
        linhas=[linha('b','2'),linha('a','1'),linha('pos','3',pos_aceite=True),linha('diag','4',condicao='diagnostico'),
                linha('r0','5',R=0),linha('f0','6',F_criterio=0),linha('sim','7',dry_run=True),linha('nao','8',status_aplicacao='sem_edicoes')]
        self.assertEqual([r['tentativa_id'] for r in conjunta.selecionar(linhas)],['a','b'])


class AplicacaoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.wt=Path(self.tmp.name)
        self.git('init','-q');self.git('config','user.email','t@t');self.git('config','user.name','t')
        self.linhas=[f'linha{i}' for i in range(20)]
        (self.wt/'a.txt').write_text(self.texto());self.git('add','.');self.git('commit','-qm','base')

    def texto(self,**trocas):
        return ''.join(trocas.get(l,l)+'\n' for l in self.linhas)

    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.wt,check=True,capture_output=True,text=True).stdout

    def diff(self,nome,novo):
        (self.wt/'a.txt').write_text(novo);p=self.wt.parent/(self.wt.name+nome)
        p.write_text(self.git('diff'));self.addCleanup(p.unlink,True);self.git('checkout','--','a.txt')
        return p

    def test_conflito_nao_interrompe_e_compativel_e_aplicado(self):
        primeiro=self.diff('1',self.texto(linha2='A'));conflito=self.diff('2',self.texto(linha2='B'));terceiro=self.diff('3',self.texto(linha17='C'))
        aplicados,conflitos=conjunta.aplicar_em_ordem(self.wt,[('p1',primeiro),('p2',conflito),('p3',terceiro)])
        self.assertEqual(aplicados,['p1','p3']);self.assertEqual([c['tentativa_id'] for c in conflitos],['p2'])
        self.assertEqual((self.wt/'a.txt').read_text(),self.texto(linha2='A',linha17='C'))


class ClassificadorTests(unittest.TestCase):
    def test_teste_ligado_a_qualquer_caso_vira_d_no_conjunto(self):
        def original(testes,arquivo=None,caso=None):
            d=[t for t in testes if (caso,t) in {('A','x'),('B','y')}]
            return {'d_marcador':[],'d_criterio':d,'f_marcador':list(testes),'f_criterio':[t for t in testes if t not in d]}
        r=conjunta.classificador_conjunto(original,['A','B'])(['x','y','z'])
        self.assertEqual(r['d_criterio'],['x','y']);self.assertEqual(r['f_criterio'],['z'])
        self.assertEqual(r['d_marcador'],[])


class ComparacaoTests(unittest.TestCase):
    def test_mcnemar_exato(self):
        self.assertEqual(comparar.mcnemar_exato(0,0),1.0)
        self.assertEqual(comparar.mcnemar_exato(5,0),0.0625)
        self.assertEqual(comparar.mcnemar_exato(1,1),1.0)

    def test_origem_da_regra(self):
        self.assertEqual(comparar.origem_regra('tcc.crypto.md5'),'regra_propria')
        self.assertEqual(comparar.origem_regra('javascript.lang.x'),'registro')

    def test_pareamento_usa_so_casos_em_comum(self):
        a={'modelo':'a','casos':[{'caso_id':c} for c in 'xyz'],'aceitos':{'x','y'}}
        b={'modelo':'b','casos':[{'caso_id':c} for c in 'xy'],'aceitos':{'x'}}
        r=comparar.pareado_modelos([a,b])[0]
        self.assertEqual((r['casos_comuns'],r['ambos'],r['so_a'],r['so_b'],r['nenhum']),(2,1,1,0,0))


if __name__=='__main__':unittest.main()
