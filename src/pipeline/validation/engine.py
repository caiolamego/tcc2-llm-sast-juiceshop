"""Medições pós-patch compartilhadas pelo experimento e replay sem LLM."""
from pathlib import Path
import json
import time

from pipeline.caminhos import RAIZ_REPO
from pipeline.sast.semgrep_client import scan_perfil, carregar_scan_perfil
from pipeline.sast.comparacao import chave_caso
from pipeline.sast.comparacao_v2 import comparar
from pipeline.validation.runner import validar, ConfigValidacao, ResultadoValidacao, ResultadoTier
from pipeline.validation.cache import CacheEvidencias
from pipeline.validation.identity import digest, hash_json, estado, ambiente, baseline_semantico, versao
from pipeline.validation.policy import opcoes
from pipeline.validation.components import componentes


def _resultado(data):
    data = dict(data)
    data['tiers'] = [ResultadoTier(**r) for r in data['tiers']]
    return ResultadoValidacao(**data)


def _falha_carregamento(tier):
    # O runner do Node também publica um testcase para um arquivo que não
    # conseguiu carregar. Isso não é evidência reutilizável de uma falha de teste.
    for nome in tier.get('testes_falhos', []):
        partes = nome.split(' :: ', 1)
        if len(partes) == 2 and partes[0] == partes[1]:
            return True
    saida = tier.get('saida', '') + tier.get('saida_reexecucao', '')
    return any(m in saida for m in ('unsatisfied precondition', 'ERR_MODULE_NOT_FOUND',
                                    'ERR_DLOPEN_FAILED', 'Cannot find module'))


def funcional_elegivel(data):
    return (not data.get('cobertura_insuficiente') and
            not data.get('testes_falhos_intermitentes') and bool(data.get('tiers'))
            and all(not r.get('timeout_na_primeira_rodada') and not _falha_carregamento(r) and
                    not any(x in (r.get('motivo') or '') for x in ('timeout','comando_nao_encontrado','falha_sem_relatorio'))
                    for r in data['tiers']))


def medir(wt, issue, fontes, baseline, perfil, baseline_testes, saida_raw, args,
          lock_api=None, origem=None, cache_dir=None, parar=lambda: False):
    inicio = time.monotonic()
    options = opcoes(args)
    wt, saida_raw = Path(wt), Path(saida_raw)
    saida_raw.parent.mkdir(parents=True, exist_ok=True)
    perfil.conferir()
    original = estado(wt)
    commit = versao(['git','-C',str(wt),'rev-parse','HEAD'])
    impl = componentes()
    cache = CacheEvidencias(cache_dir or RAIZ_REPO/'.cache/validacao/v1', options['cache_validacao'], parar)
    meta, tempos, holder = {}, {}, {}
    identidade_sast = {'estado':original,'commit':commit,'perfil':perfil.hash,'baseline':baseline_semantico(baseline),
                       'implementacao':impl, 'semgrep':perfil.dados['semgrep_versao']}

    def conferir_sast():
        perfil.conferir()
        return estado(wt) == original

    def obter_scan():
        if holder: return
        t = time.monotonic()
        def calcular():
            scan = scan_perfil(wt,perfil,saida_raw,args.semgrep_bin)
            return {'raw':saida_raw.read_text() if saida_raw.exists() else None,
                    'stderr':saida_raw.with_suffix('.stderr.log').read_text() if saida_raw.with_suffix('.stderr.log').exists() else '',
                    'falha_operacional':scan.falha_operacional,
                    'duracao_original_s':time.monotonic()-t}
        data, info = cache.obter('sast', identidade_sast, calcular, conferir_sast,
                                 lambda d: bool(d.get('raw')) and not d.get('falha_operacional'), origem)
        tempos['sast_s'] = time.monotonic()-t
        if data['raw']:
            # Materializa inclusive no hit, preservando bytes e hashes da evidência.
            saida_raw.write_text(data['raw'], encoding='utf-8')
            saida_raw.with_suffix('.stderr.log').write_text(data['stderr'], encoding='utf-8')
            scan = carregar_scan_perfil(saida_raw,wt,perfil)
            scan.falha_operacional = data['falha_operacional']
        else:
            from pipeline.sast.semgrep_client import ScanResultado
            scan = ScanResultado([],[],perfil.dados['semgrep_versao'],data['falha_operacional'])
        info['duracao_original_s'] = data['duracao_original_s']
        meta['sast'] = info
        t = time.monotonic()
        holder['scan'] = scan
        holder['comparacao'] = comparar(baseline,scan,chave_caso(issue),fontes,checkout=wt)
        tempos['comparacao_s'] = time.monotonic()-t

    cfg = ConfigValidacao(lock_t4=lock_api, arquivo_linha_de_base=Path(baseline_testes),
                          politica=options['politica_validacao'], mapa=options['mapa_testes'],
                          repeticao_api=options['repeticao_api'])
    cfg.cobertura=options.get('cobertura_funcional')
    def ambiente_funcional():
        if cfg.cobertura:
            from pipeline.validation.coverage import ambiente as ambiente_cobertura
            return ambiente_cobertura(wt,(wt/'frontend/node_modules').is_dir())
        return ambiente(wt)
    if cfg.politica == 'historica_v1':
        obter_scan()
    t = time.monotonic()
    # Mesmo arquivos ignorados participam da identidade funcional. Mudanças
    # produzidas por testes impedem publicação se não forem reproduzíveis.
    cache_func = cache
    bypass = None
    try:
        funcional = estado(wt, funcional=True) if options['cache_validacao'] != 'desligado' else None
        env = ambiente_funcional() if options['cache_validacao'] != 'desligado' else None
    except (ValueError,OSError) as exc:
        funcional,env = None,None
        bypass = f'identidade_funcional_indisponivel: {type(exc).__name__}'
        cache_func = CacheEvidencias(cache.raiz,'desligado',parar)
    identidade_func = {'estado':funcional, 'commit':commit,'ambiente':env, 'baseline':digest(baseline_testes),
                      'politica':cfg.politica, 'repeticao':cfg.repeticao_api,
                      'mapa':digest(cfg.mapa) if cfg.mapa else None, 'implementacao':impl,
                      'conjunto_d':digest(RAIZ_REPO/'config/conjunto_d.json'),
                      'arquivos':sorted(fontes),'timeouts':[cfg.timeout_t0_s,cfg.timeout_t2_s,cfg.timeout_t3_s,cfg.timeout_t4_s]}
    if cfg.cobertura:
        from pipeline.validation.coverage import carregar,identidade as identidade_cobertura
        revision=carregar(cfg.cobertura,cfg.mapa,wt,permitir_avaliadores_alterados=True)
        identidade_func['cobertura']=identidade_cobertura(revision,cfg.cobertura,cfg.mapa)
    tempos['identidade_funcional_s'] = time.monotonic()-t
    t = time.monotonic()
    def conferir_func():
        cobertura_ok=(not cfg.cobertura or identidade_cobertura(
            carregar(cfg.cobertura,cfg.mapa,wt,permitir_avaliadores_alterados=True),cfg.cobertura,cfg.mapa)==identidade_func['cobertura'])
        return (cobertura_ok and componentes()==impl and estado(wt,funcional=True) == funcional and ambiente_funcional() == env
                and digest(baseline_testes) == identidade_func['baseline']
                and (digest(cfg.mapa) if cfg.mapa else None) == identidade_func['mapa'])
    def calcular_func():
        return validar(wt,list(fontes),cfg,entre_etapas=obter_scan if cfg.politica != 'historica_v1' else None).to_dict()
    data, info = cache_func.obter('funcional',identidade_func,calcular_func,conferir_func,funcional_elegivel,origem)
    if bypass:info['motivo']=bypass
    tempos['validacao_s'] = time.monotonic()-t - (tempos.get('sast_s',0)+tempos.get('comparacao_s',0) if cfg.politica != 'historica_v1' and not info['hit'] else 0)
    info['duracao_original_s'] = data['duracao_s']
    meta['funcional'] = info
    evidencia_funcional = saida_raw.with_name(saida_raw.stem+'_evidencia_funcional.json')
    evidencia_funcional.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    info['evidencia_sha256'] = digest(evidencia_funcional)
    etapas_atuais = []
    for etapa in data.get('etapas',[]):
        atual = dict(etapa)
        if info['hit'] and atual['status']=='executada':
            atual.update(status='reutilizada',duracao_original_s=atual['duracao_s'],duracao_s=0.)
        etapas_atuais.append(atual)
    tempos['espera_api_s'] = 0 if info['hit'] else sum(r.get('espera_api_s',0) for r in data['tiers'])
    tempos['selecao_s'] = 0 if info['hit'] else data.get('duracao_selecao_s',0)
    tempos['triagem_s'] = 0 if info['hit'] else sum(r['duracao_s'] for r in data['tiers'] if r['tier'] in ('T0','T2','T2_API'))
    tempos['ampla_s'] = 0 if info['hit'] else sum(r['duracao_s'] for r in data['tiers'] if r['tier'] in ('T3','T4'))
    obter_scan()  # Hits funcionais não dispensam SAST nem o comparador da ocorrência.
    if not conferir_sast():
        raise ValueError('Código/perfil alterado durante medição pós-patch')
    if (componentes() != impl or
            digest(RAIZ_REPO/'config/conjunto_d.json') != identidade_func['conjunto_d'] or
            digest(baseline_testes) != identidade_func['baseline'] or
            (digest(cfg.mapa) if cfg.mapa else None) != identidade_func['mapa']):
        raise ValueError('Configuração/implementação alterada durante a medição')
    if cfg.cobertura and identidade_cobertura(carregar(cfg.cobertura,cfg.mapa,wt,permitir_avaliadores_alterados=True),cfg.cobertura,cfg.mapa)!=identidade_func['cobertura']:
        raise ValueError('Revisão/conjunto D/avaliações alteradas durante medição')
    tempos['total_s'] = time.monotonic()-inicio
    metadata={'cache_validacao':meta,'tempos_medicao':tempos,
                                                               'etapas_validacao':etapas_atuais,
                                                               'politica_validacao':cfg.politica,
                                                               'cobertura_funcional':('insuficiente' if data.get('cobertura_insuficiente') else
                                                                                      'relacionada_v2' if cfg.politica == 'relacionada_v2' else
                                                                                      'servidor_relacionado' if cfg.politica == 'relacionada_v1' else 'servidor')}
    if cfg.cobertura:
        metadata['cobertura_detalhada']=data.get('cobertura_detalhada')
        metadata['selecao_testes']=data.get('selecao')
    return holder['scan'],holder['comparacao'],_resultado(data),metadata
