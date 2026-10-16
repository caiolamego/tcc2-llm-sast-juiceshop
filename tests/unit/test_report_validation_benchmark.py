"""Consolidação do benchmark usa evidência estática; não executa o alvo."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.reports.report_validation_benchmark import comparar, publicar


def run(nome, tempo):
    row={'caso_id':'AMP1','estrategia':'P1','repeticao':1,'patch_sha256':'patch',
         'R':1,'M':1,'F_criterio':1,'F_marcador':0,'F_sem_separacao':0,
         'falhas_persistentes':['A','B'],'falhas_intermitentes':[],
         'cache_validacao':{'sast':{'hit':False},'funcional':{'hit':False}}}
    manifest={'commit_alvo':'commit','validacao':{'implementacao':{'runner':'hash'},
               'politica_validacao':'historica_v1' if 'REF' in nome else 'otimizada_v1'},
              'k':1,'tempo_parede_execucao_s':tempo,'preparacao_s':10}
    return {'nome':nome,'manifesto':manifest,'rows':[row]}


class ReportBenchmarkTests(unittest.TestCase):
    def test_mediana_ganho_e_populacao_de_replay(self):
        runs=[run(f'R{r}_REF_K1',t) for r,t in enumerate([100,120,110],1)]
        runs += [run(f'R{r}_OPT_FRIO_K1',t) for r,t in enumerate([50,60,55],1)]
        report=comparar(runs,'R1_REF_K1')
        self.assertEqual(report['comparacoes_tempo'][0]['razao_mediana'],2)
        self.assertTrue(report['comparacoes_tempo'][0]['tres_repeticoes'])
        self.assertEqual(report['divergencias'],[])
        self.assertEqual(report['chamadas_llm'],0)

    def test_ambiguidade_preservada_e_divergencia_seletiva_visivel(self):
        a,b=run('R1_REF_K1',10),run('SELETIVA_K1',8)
        a['rows'][0].update(R=None,M=None)
        b['rows'][0].update(R=None,M=None,F_sem_separacao=1)
        report=comparar([a,b],a['nome'])
        self.assertEqual(len(report['divergencias']),1)
        self.assertEqual(report['divergencias'][0]['campo'],'F_sem_separacao')

    def test_ordem_das_falhas_nao_e_divergencia(self):
        a,b=run('R1_REF_K1',10),run('R1_OPT_FRIO_K1',8)
        b['rows'][0]['falhas_persistentes'].reverse()
        self.assertEqual(comparar([a,b],a['nome'])['divergencias'],[])

    def test_fontes_cientificas_diferentes_recusadas(self):
        a,b=run('R1_REF_K1',10),run('R1_OPT_FRIO_K1',8)
        for mutacao in ('patch','populacao','implementacao'):
            alterado=deepcopy(b)
            if mutacao=='patch':alterado['rows'][0]['patch_sha256']='outro'
            elif mutacao=='populacao':alterado['rows'][0]['caso_id']='AMP2'
            else:alterado['manifesto']['validacao']['implementacao']['runner']='outro'
            with self.subTest(mutacao=mutacao),self.assertRaises(ValueError):comparar([a,alterado],a['nome'])

    def test_publicacao_deterministica_e_sem_sobrescrita(self):
        report=comparar([run('R1_REF_K1',10)],'R1_REF_K1')
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            publicar(base/'a',report,base,{})
            publicar(base/'b',report,base,{})
            for f in (base/'a').iterdir():self.assertEqual(f.read_bytes(),(base/'b'/f.name).read_bytes())
            with self.assertRaises(ValueError):publicar(base/'a',report,base,{})


if __name__=='__main__':unittest.main()
