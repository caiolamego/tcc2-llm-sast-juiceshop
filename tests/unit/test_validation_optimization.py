"""Feature 05: processos do alvo/LLM/SAST substituídos por fixtures e mocks."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from pipeline.etapas.e07_validacao.cache import CacheEvidencias
from pipeline.comum.identidade import hash_json, estado, dependencias
from pipeline.etapas.e07_validacao.selecao import selecionar
from pipeline.etapas.e07_validacao.camadas import ResultadoTier, ConfigValidacao, validar, _avaliar
from pipeline.etapas.e07_validacao.politicas import opcoes, alterada
from pipeline.etapas.e07_validacao.repeticao import repetir_seletivo
from pipeline.etapas.e07_validacao.medicao import funcional_elegivel
from pipeline.etapas.e09_metricas.calculo import custos_atual


class OptimizationTests(unittest.TestCase):
    def test_cancelamento_durante_espera_nao_publica_cache(self):
        import fcntl
        from unittest.mock import Mock
        cache = CacheEvidencias(self.root/'cache', 'leitura-escrita', parar=lambda: True)
        pasta = cache.raiz/'sast'
        pasta.mkdir(parents=True)
        chave = hash_json({'estado': 'ocupado'})
        calcular = Mock()
        with (pasta/(chave+'.lock')).open('a') as dono:
            fcntl.flock(dono.fileno(), fcntl.LOCK_EX)
            with self.assertRaises(InterruptedError):
                cache.obter('sast', {'estado': 'ocupado'}, calcular, lambda: True,
                            lambda _: True, 'fixture')
        calcular.assert_not_called()
        self.assertFalse((pasta/chave).exists())

    def test_cache_recusa_falha_de_carregamento_com_junit(self):
        data = {'tiers': [{'testes_falhos': ['test/api/key.test.ts :: test/api/key.test.ts']}]}
        self.assertFalse(funcional_elegivel(data))
        data['tiers'] = [{'saida': 'Exiting due to unsatisfied precondition!'}]
        self.assertFalse(funcional_elegivel(data))
        data['tiers'] = [{'testes_falhos': ['test/api/key.test.ts :: key > denies traversal']}]
        self.assertTrue(funcional_elegivel(data))

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.mapa=self.root/'mapa.yaml'
        for f in ('test/server/key.unit.test.ts','test/api/key.test.ts','routes/key.ts'):
            p=self.root/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
        self.mapa.write_text('''schema_versao: '1.0'
arquivos:
  routes/key.ts:
    modo: relacionados
    justificativa: Fixture revisada
    unitarios: [test/server/key.unit.test.ts]
    api: [test/api/key.test.ts]
''')

    def test_selecao_uniao_e_fallback(self):
        s=selecionar(self.mapa,self.root,['routes/key.ts','routes/key.ts'])
        self.assertFalse(s.fallback);self.assertEqual(len(s.api),1)
        s=selecionar(self.mapa,self.root,['routes/key.ts','lib/shared.ts'])
        self.assertTrue(s.fallback);self.assertIn('lib/shared.ts',s.motivos[0])
        self.assertTrue(selecionar(self.mapa,self.root,[]).fallback)

    def test_mapa_chaves_duplicadas_testes_ausentes_e_escape(self):
        original=self.mapa.read_text()
        for content in (original+'arquivos: {}\n', original.replace('test/api/key.test.ts','test/api/ausente.test.ts'),
                        original.replace('test/api/key.test.ts','../fora.ts')):
            with self.subTest(content=content):
                self.mapa.write_text(content)
                with self.assertRaises(ValueError):selecionar(self.mapa,self.root,['routes/key.ts'])

    def test_symlink_externo_rejeitado(self):
        with tempfile.TemporaryDirectory() as other:
            (self.root/'test/api/key.test.ts').unlink()
            (self.root/'test/api/key.test.ts').symlink_to(Path(other)/'x')
            with self.assertRaises(ValueError):selecionar(self.mapa,self.root,['routes/key.ts'])

    def test_identidade_funcional_inclui_ignorados(self):
        a=estado(self.root,funcional=True)
        (self.root/'config.local').write_text('novo')
        self.assertNotEqual(a,estado(self.root,funcional=True))

    def test_dependencias_invalidam_por_conteudo(self):
        deps=self.root/'node_modules';deps.mkdir();p=deps/'x.js';p.write_text('a')
        a=dependencias(deps);self.assertEqual(a,dependencias(deps))
        p.write_text('b');self.assertNotEqual(a,dependencias(deps))

    def test_cache_concorrente_publica_uma_medicao(self):
        cache=CacheEvidencias(self.root/'cache','leitura-escrita');calls=[]
        def calcular():calls.append(1);time.sleep(.02);return {'ok':True}
        def rodar():return cache.obter('sast',{'code':'x'},calcular,lambda:True,lambda d:d.get('ok'),{'teste':True})
        with ThreadPoolExecutor(2) as executor:result=list(executor.map(lambda _:rodar(),range(2)))
        self.assertEqual(len(calls),1);self.assertEqual(sum(r[1]['hit'] for r in result),1)
        self.assertEqual(result[0][0],result[1][0])

    def test_cache_adulterado_recalculado_e_nao_sobrescreve_valido(self):
        cache=CacheEvidencias(self.root/'cache','leitura-escrita');calls=[]
        def calcular():calls.append(1);return {'ok':True}
        def obter():return cache.obter('sast',{'x':1},calcular,lambda:True,lambda d:d.get('ok'),{'id':'A'})
        obter();raw=self.root/'cache/sast'/hash_json({'x':1})/'resultado.json'
        raw.write_text('{}')
        _,meta=obter();self.assertFalse(meta['hit']);self.assertEqual(len(calls),2)
        _,meta=obter();self.assertTrue(meta['hit']);self.assertEqual(len(calls),2)

    def test_cache_nao_publica_estado_alterado_ou_falha(self):
        cache=CacheEvidencias(self.root/'cache','leitura-escrita')
        for valido in (False,True):
            _,meta=cache.obter('f',{'valido':valido},lambda:{'ok':valido},lambda:False,lambda d:d['ok'],{})
            self.assertFalse(meta.get('publicado',False))

    def test_cache_leitura_nao_publica_e_identidade_diferente_miss(self):
        for key in ('a','b'):
            cache=CacheEvidencias(self.root/'cache','leitura')
            _,m=cache.obter('f',{'code':key},lambda:{'ok':True},lambda:True,lambda _:True,{})
            self.assertFalse(m['hit']);self.assertFalse(m.get('publicado',False))

    def test_cache_falha_de_escrita_limpa_temporario(self):
        cache=CacheEvidencias(self.root/'cache','leitura-escrita')
        with patch('pipeline.etapas.e07_validacao.cache.os.rename',side_effect=OSError('disco')):
            with self.assertRaises(OSError):cache.obter('f',{},lambda:{'ok':True},lambda:True,lambda _:True,{})
        self.assertFalse(list((self.root/'cache/f').glob('*.tmp-*')))

    def test_opcoes_invalidas_e_obrigatoriedade_do_mapa(self):
        self.assertFalse(alterada(SimpleNamespace()))
        with self.assertRaises(ValueError):opcoes(SimpleNamespace(politica_validacao='otimizada_v1'))
        with self.assertRaises(ValueError):opcoes(SimpleNamespace(cache_validacao='outro'))

    def test_triagem_reprovada_mede_sast_e_dispensa_amplas(self):
        cfg=ConfigValidacao(politica='otimizada_v1',mapa=self.mapa)
        eventos=[]
        with patch('pipeline.etapas.e07_validacao.camadas.carregar_linha_de_base',return_value={'T3':set(),'T4':set()}), \
             patch('pipeline.etapas.e07_validacao.camadas._t0',return_value=ResultadoTier('T0',[],False,1,'falha')), \
             patch('pipeline.etapas.e07_validacao.camadas.rodar_suite') as ampla:
            resultado=validar(self.root,['routes/key.ts'],cfg,entre_etapas=lambda:eventos.append('sast'))
        ampla.assert_not_called();self.assertEqual(eventos,['sast']);self.assertFalse(resultado.F_criterio)
        self.assertTrue(any(e['status']=='dispensada_por_reprovacao' for e in resultado.etapas))

    def test_triagem_aprovada_exige_amplas_e_ordem(self):
        cfg=ConfigValidacao(politica='otimizada_v1',mapa=self.mapa)
        eventos=[]
        def ok(tier):eventos.append(tier);return ResultadoTier(tier,[],True,.1)
        with patch('pipeline.etapas.e07_validacao.camadas.carregar_linha_de_base',return_value={'T3':set(),'T4':set()}), \
             patch('pipeline.etapas.e07_validacao.camadas._t0',side_effect=lambda *_:ok('T0')), \
             patch('pipeline.etapas.e07_validacao.camadas.rodar_t2',side_effect=lambda *_:ok('T2')), \
             patch('pipeline.etapas.e07_validacao.camadas._api_relacionada',side_effect=lambda *_:ok('T2_API')), \
             patch('pipeline.etapas.e07_validacao.camadas.rodar_suite',side_effect=lambda tier,*_:ok(tier)):
            resultado=validar(self.root,['routes/key.ts'],cfg,entre_etapas=lambda:eventos.append('SAST'))
        self.assertEqual(eventos,['T0','T2','T2_API','SAST','T3','T4']);self.assertTrue(resultado.F_criterio)

    def validar_relacionada(self, arquivos, api=None, t0=None, rodar_api=True):
        cfg = ConfigValidacao(politica='relacionada_v1', mapa=self.mapa, rodar_t4=rodar_api)
        eventos = []
        def ok(tier):
            eventos.append(tier)
            return ResultadoTier(tier, [], True, .1)
        with patch('pipeline.etapas.e07_validacao.camadas.carregar_linha_de_base', return_value={}), \
             patch('pipeline.etapas.e07_validacao.camadas._t0', side_effect=lambda *_: t0 or ok('T0')), \
             patch('pipeline.etapas.e07_validacao.camadas.rodar_t2', side_effect=lambda *_: ok('T2')), \
             patch('pipeline.etapas.e07_validacao.camadas._api_relacionada', side_effect=lambda *_: api or ok('T2_API')), \
             patch('pipeline.etapas.e07_validacao.camadas.rodar_suite') as ampla, \
             patch('pipeline.etapas.e07_validacao.camadas._t4_serializado') as t4:
            res = validar(self.root, arquivos, cfg, entre_etapas=lambda: eventos.append('SAST'))
        ampla.assert_not_called()
        t4.assert_not_called()
        return res, eventos

    def test_relacionada_nao_exige_suite_ampla_para_aprovar(self):
        res, eventos = self.validar_relacionada(['routes/key.ts'])
        self.assertEqual(eventos, ['T0', 'T2', 'T2_API', 'SAST'])
        self.assertTrue(res.F_criterio)
        self.assertEqual(res.escopo, 'relacionado')
        self.assertFalse(res.cobertura_insuficiente)
        self.assertEqual([e['status'] for e in res.etapas[-2:]], ['nao_aplicavel']*2)

    def test_relacionada_sem_unitario_usa_api_mapeada(self):
        self.mapa.write_text(self.mapa.read_text().replace('unitarios: [test/server/key.unit.test.ts]', 'unitarios: []'))
        res, eventos = self.validar_relacionada(['routes/key.ts'])
        self.assertEqual(eventos, ['T0', 'T2_API', 'SAST'])
        self.assertTrue(res.F_criterio)

    def test_relacionada_lacunas_nao_disparam_amplas_nem_aprovacao(self):
        for arquivos in ([], ['lib/shared.ts'], ['routes/key.ts', 'lib/shared.ts']):
            with self.subTest(arquivos=arquivos):
                res, eventos = self.validar_relacionada(arquivos)
                self.assertTrue(res.cobertura_insuficiente)
                self.assertIsNone(res.passou)
                self.assertTrue(all(getattr(res, 'F_'+d) is None for d in ('criterio','marcador','sem_separacao')))
                self.assertIn('SAST', eventos)
                self.assertFalse(funcional_elegivel(res.to_dict()))

    def test_relacionada_falha_compilacao_preserva_sast_e_f_negativo(self):
        res, eventos = self.validar_relacionada(['lib/shared.ts'], t0=ResultadoTier('T0', [], False, .1, 'falha'))
        self.assertEqual(eventos, ['SAST'])
        self.assertFalse(res.F_criterio)
        self.assertTrue(res.cobertura_insuficiente)

    def test_relacionada_api_desligada_nao_inventa_cobertura(self):
        res, eventos = self.validar_relacionada(['routes/key.ts'], rodar_api=False)
        self.assertNotIn('T2_API', eventos)
        self.assertIsNone(res.F_criterio)

    def test_relacionada_preserva_definicoes_f_d(self):
        nome = 'test/api/key.test.ts :: Suite > desafio'
        falha = ResultadoTier('T2_API', [], False, .1, 'falha', testes_falhos_novos=[nome])
        with patch('pipeline.etapas.e07_validacao.camadas.classificar', return_value={
                'd_marcador': [], 'd_criterio': [nome], 'f_marcador': [nome], 'f_criterio': []}):
            res, eventos = self.validar_relacionada(['routes/key.ts'], api=falha)
        self.assertTrue(res.F_criterio)
        self.assertFalse(res.F_marcador)
        self.assertFalse(res.F_sem_separacao)
        self.assertIn('SAST', eventos)

    def test_fallback_nao_duplica_suites(self):
        cfg=ConfigValidacao(politica='otimizada_v1',mapa=self.mapa)
        with patch('pipeline.etapas.e07_validacao.camadas.carregar_linha_de_base',return_value={}), \
             patch('pipeline.etapas.e07_validacao.camadas._t0',return_value=ResultadoTier('T0',[],True,0)), \
             patch('pipeline.etapas.e07_validacao.camadas.rodar_suite',side_effect=lambda t,*_:ResultadoTier(t,[],True,0)) as ampla:
            result=validar(self.root,['lib/shared.ts'],cfg)
        self.assertEqual(ampla.call_count,2);self.assertTrue(result.selecao['fallback'])

    def test_repeticao_seletiva_incompleta_faz_fallback(self):
        falha=ResultadoTier('T4',[],False,1,'falha',testes_falhos_novos=['test/api/key.test.ts :: Suite > teste'])
        with patch('pipeline.etapas.e07_validacao.camadas._uma_rodada',return_value=ResultadoTier('T4',[],True,1)), \
             patch('pipeline.etapas.e07_validacao.repeticao.executados',return_value=[]):
            resultado,meta=repetir_seletivo(falha,self.root,10,{},set())
        self.assertIsNone(resultado);self.assertIn('incompleta',meta['fallback'])

    def test_repeticao_seletiva_confere_identidades_e_hooks(self):
        ident='test/api/key.test.ts :: Suite > teste [especial]'
        falha=ResultadoTier('T4',[],False,1,'falha',testes_falhos_novos=[ident])
        with patch('pipeline.etapas.e07_validacao.camadas._uma_rodada',return_value=ResultadoTier('T4',[],True,1)) as rodada, \
             patch('pipeline.etapas.e07_validacao.repeticao.executados',return_value=[ident]):
            resultado,meta=repetir_seletivo(falha,self.root,10,{},set())
        self.assertIsNotNone(resultado);cmd=rodada.call_args.args[1]
        self.assertIn('--import',cmd);self.assertTrue(any('\\[especial\\]' in arg for arg in cmd))

    def test_dependencia_de_ordem_pode_divergir_e_nao_muda_padrao(self):
        ident='test/api/key.test.ts :: Suite > depende da ordem'
        primeira=ResultadoTier('T4',[],False,1,'falha',testes_falhos_novos=[ident])
        ampla=deepcopy(primeira)
        with patch('pipeline.etapas.e07_validacao.camadas._uma_rodada',side_effect=[deepcopy(primeira),ampla]):
            referencia=_avaliar('T4',[],self.root,10,{},self.root/'xml',set())
        with patch('pipeline.etapas.e07_validacao.camadas._uma_rodada',return_value=deepcopy(primeira)), \
             patch('pipeline.etapas.e07_validacao.repeticao.repetir_seletivo',return_value=(ResultadoTier('T4',[],True,1),{})):
            experimental=_avaliar('T4',[],self.root,10,{},self.root/'xml',set(),seletiva=True)
        self.assertFalse(referencia.passou);self.assertTrue(experimental.passou)
        self.assertEqual(opcoes(SimpleNamespace())['repeticao_api'],'ampla')

    def test_falha_intermitente_nao_e_cacheavel(self):
        self.assertFalse(funcional_elegivel({'tiers':[{}],'testes_falhos_intermitentes':['x']}))
        self.assertFalse(funcional_elegivel({'tiers':[{'motivo':'timeout'}]}))
        self.assertTrue(funcional_elegivel({'tiers':[{'motivo':'falha'}]}))

    def test_metricas_cache_validacao_nao_altera_cobranca_llm(self):
        row={'dry_run':False,'do_cache':False,'custo_usd':.1,'tokens_entrada':1,'tokens_saida':1,
             'duracao_llm_s':1,'duracao_sast_s':.1,'duracao_validacao_s':.1,
             'cache_validacao':{'sast':{'hit':True,'duracao_original_s':20},'funcional':{'hit':True,'duracao_original_s':40}}}
        r=custos_atual([row],[])
        self.assertEqual(r['chamadas_novas_registradas'],1);self.assertEqual(r['usos_cache'],0)
        self.assertEqual(r['validacao_reutilizada']['sast']['reusos'],1)
        self.assertEqual(r['tempos_acumulados']['duracao_sast_s']['total_conhecido'],.1)

    def test_mesmo_scan_reutilizado_recalcula_r_por_ocorrencia(self):
        from pipeline.etapas.e07_validacao.medicao import medir
        from pipeline.etapas.e07_validacao.camadas import ResultadoValidacao
        from pipeline.etapas.e01_analise_sast.semgrep import carregar_scan_perfil
        raw={'version':'fixture','results':[
            {'check_id':'rule','path':'routes/key.ts','start':{'line':2,'col':1},
             'end':{'line':2,'col':2},'extra':{}}]}
        perfil=SimpleNamespace(hash='perfil',dados={'id_regras':['rule'],'semgrep_versao':'fixture'},
                               conferir=lambda:None,no_escopo=lambda _:True)
        baseline_file=self.root/'baseline.json'
        before=deepcopy(raw);first=deepcopy(raw['results'][0]);first['start']['line']=1;first['end']['line']=1
        before['results'].append(first);baseline_file.write_text(json.dumps(before))
        baseline=carregar_scan_perfil(baseline_file,self.root,perfil)
        args=SimpleNamespace(semgrep_bin='fixture',cache_validacao='leitura-escrita')
        def scan(wt,perfil,path,bin):
            path.write_text(json.dumps(raw));return carregar_scan_perfil(path,wt,perfil)
        val=ResultadoValidacao(True,None,3,F_sem_separacao=True,F_marcador=True,F_criterio=True,
                               tiers=[ResultadoTier('T0',[],True,3)])
        def issue(line):return {'check_id':'rule','arquivo':'routes/key.ts','linha_inicio':line,
                                'linha_fim':line,'coluna_inicio':1,'coluna_fim':2}
        with patch('pipeline.etapas.e07_validacao.medicao.estado',return_value='estado'), \
             patch('pipeline.etapas.e07_validacao.medicao.versao',return_value='commit'), \
             patch('pipeline.etapas.e07_validacao.medicao.ambiente',return_value={}), \
             patch('pipeline.etapas.e07_validacao.medicao.scan_perfil',side_effect=scan) as scan_mock, \
             patch('pipeline.etapas.e07_validacao.medicao.validar',return_value=val) as validar_mock:
            a=medir(self.root,issue(1),{},baseline,perfil,baseline_file,self.root/'a/raw.json',args,
                    cache_dir=self.root/'cache')
            b=medir(self.root,issue(2),{},baseline,perfil,baseline_file,self.root/'b/raw.json',args,
                    cache_dir=self.root/'cache')
        self.assertEqual(a[1]['R'],1);self.assertEqual(b[1]['R'],0)
        self.assertEqual(scan_mock.call_count,1);self.assertEqual(validar_mock.call_count,1)
        self.assertTrue(b[3]['cache_validacao']['sast']['hit'])

    def test_benchmark_recusa_destino_existente_sem_altera_lo(self):
        from scripts.experimento.replay_patches import replay
        from pipeline.comum.caminhos import RAIZ_REPO
        # Caminho sintético sob a raiz esperada, sem criar artefatos no repositório.
        destino=RAIZ_REPO/'outputs/feature05/JA_EXISTE'
        args=SimpleNamespace(origem=RAIZ_REPO/'outputs/origem',saida=destino)
        with patch.object(Path,'exists',return_value=True),patch.object(Path,'write_text') as escrita:
            with self.assertRaisesRegex(ValueError,'Destino já existe'):replay(args)
        escrita.assert_not_called()


if __name__=='__main__':unittest.main()
