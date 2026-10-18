"""Leitura estrita e proveniência portátil; nenhuma execução de scans/LLM."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re

from pipeline.caminhos import RAIZ_REPO
from pipeline.catalogo import carregar as carregar_catalogo
from pipeline.metrics import exigir, digest, ler_json, relativo, _pares
from pipeline.metrics.normalizer import DEFS, normalizar_atual
from pipeline.prompts.builder import ESTRATEGIAS, DIAGNOSTICOS


@dataclass
class Entrada:
    raiz: Path
    execucao: str
    catalogo: object
    contrato: dict | None
    linhas: list[dict]
    sessoes: list[dict]
    preflight: dict | None
    fontes: dict = field(default_factory=dict)
    arquivos: dict = field(default_factory=dict)
    avisos: list = field(default_factory=list)
    perfil: object | None = None

    def registrar(self, path, role):
        path = path.resolve()
        old = digest(path)
        exigir(role not in self.fontes or self.fontes[role] == old, 'Papel de fonte duplicado')
        self.fontes[role] = old
        self.arquivos[path] = old

    def revalidar(self):
        for path, old in self.arquivos.items():
            exigir(path.is_file() and digest(path) == old, 'Entrada alterada durante a consolidação')


def estrategia(row):
    nomes = {v:k for k,v in {**ESTRATEGIAS, **DIAGNOSTICOS}.items()}
    value = row.get('estrategia_prompt',row.get('estrategia'))
    if value is not None:
        exigir(value in nomes or value in ESTRATEGIAS or value in DIAGNOSTICOS, 'Estratégia inválida')
        result = nomes.get(value, value)
    else:
        candidates = re.findall(r'(?:^|_)(P[1-4]|P1L)(?=_|$)', row.get('tentativa_id', ''))
        exigir(len(candidates) == 1, 'Identificação histórica de estratégia ambígua')
        result = candidates[0]
    condition = row.get('condicao')
    exigir(condition is None or condition == ('diagnostico' if result == 'P1L' else 'desenho'), 'Condição/estratégia divergente')
    return result


def validar_valores(row):
    for key in ('R','F','M',*(f'F_{d}' for d in DEFS)):
        value = row.get(key)
        exigir(value is None or (type(value) is int and value in (0,1)), f'{key} inválido')
    for key in ('dry_run','do_cache'):
        exigir(key not in row or type(row[key]) is bool, f'{key} inválido')
    exigir(isinstance(row.get('status_aplicacao'), str), 'Status de aplicação ausente')
    for key in ('classificacao_final',*(f'classificacao_{d}' for d in DEFS)):
        value = row.get(key)
        exigir(value is None or isinstance(value,str), 'Classificação inválida')


def _perfil(entrada):
    from pipeline.sast.perfil import carregar, digest_regras
    local = entrada.raiz/'perfil_sast/perfil.json'
    candidates = ([local] if local.exists() else
                  sorted((RAIZ_REPO/'config/perfis').glob('*/perfil.json')) +
                  sorted((RAIZ_REPO/'outputs').glob('feature*/preparacao/perfil_sast/perfil.json')))
    target = entrada.contrato['perfil_sha256']
    profile = found = None
    for candidate in candidates:
        if not candidate.is_file() or digest(candidate) != target:
            continue
        data = ler_json(candidate)
        configs = [(relativo(candidate.parent,c['arquivo']),c) for c in data.get('configs',[])]
        invalid = [(p,c) for p,c in configs if digest_regras(p) != c['sha256']]
        if invalid:
            exigir(not local.exists(), 'Snapshot local de perfil adulterado')
            for file,config in invalid:
                entrada.avisos.append({'tipo':'perfil_checkout_divergente','arquivo':config['arquivo'],
                                       'esperado':config['sha256'],'observado':digest(file)})
                entrada.registrar(file,'perfil/divergencia/'+config['arquivo'])
            continue
        profile = carregar(candidate);found=candidate
        break
    exigir(profile is not None, 'Snapshot verificável do perfil congelado ausente')
    exigir(profile.dados['semgrep_versao'] == entrada.contrato['semgrep_versao'], 'Versão do perfil divergente')
    entrada.registrar(found,'perfil/manifesto')
    for c in profile.dados['configs']:
        file = relativo(found.parent,c['arquivo'])
        entrada.registrar(file, 'perfil/'+c['arquivo'])
        sidecar = file.with_suffix(file.suffix + '.sanitizacao.json')
        if sidecar.exists():
            entrada.registrar(sidecar, 'perfil/sanitizacao/'+c['arquivo'])
            entrada.avisos.append({'tipo':'perfil_snapshot_sanitizado','arquivo':c['arquivo'],
                                   'sha256_historico':c['sha256'],'sha256_sanitizado':digest(file)})
    entrada.perfil = profile


def _cobertura(entrada):
    root=entrada.raiz/'cobertura_funcional'
    manifest=relativo(root,'manifesto.json');data=ler_json(manifest)
    exigir(data.get('schema_versao')=='1.0' and isinstance(data.get('fontes_sha256'),dict),'Snapshot funcional inválido')
    entrada.registrar(manifest,'cobertura/manifesto')
    expected=entrada.contrato['validacao']['cobertura']
    for name,field in (('revisao.yaml','revisao_sha256'),('mapa.yaml','mapa_sha256'),('conjunto_d.json','conjunto_d_sha256')):
        exigir(data['fontes_sha256'].get(name)==expected[field],'Snapshot/hash de cobertura divergente')
    exigir(data['fontes_sha256'].get('baseline/baseline_testes.json')==entrada.contrato['baseline_testes_sha256'],'Baseline portátil divergente')
    for name,h in data['fontes_sha256'].items():
        p=relativo(root,name);exigir(digest(p)==h,'Snapshot funcional adulterado')
        entrada.registrar(p,'cobertura/'+name)
    baseline=ler_json(root/'baseline/baseline_testes.json')
    for name,h in baseline.get('artefatos_sha256',{}).items():
        exigir(data['fontes_sha256'].get('baseline/'+name)==h,'Closure das evidências baseline divergente')


def _validar_contrato(entrada):
    c = entrada.contrato; cat = entrada.catalogo
    exigir(c.get('schema_versao') in ('1.0','2.0','3.0','4.0','5.0') and c.get('execucao') == entrada.execucao, 'Schema/execução do contrato inválido')
    if c.get('schema_versao')=='5.0':
        inf=c.get('inferencia')
        exigir(c.get('contrato_validacao_versao') in ('3.0','4.0'), 'Contexto de validação v5 ausente')
        exigir(isinstance(inf,dict) and inf.get('provedor') in ('openai','colab','simulado') and isinstance(inf.get('modelo'),str), 'Identidade de inferência ausente')
        if inf['provedor']=='colab':
            from pipeline.llm.colab_protocol import sha, validar_manifesto
            validar_manifesto({'schema_versao':'1.0','cientifica':inf.get('cientifica'),
                'identidade_sha256':inf.get('modelo_identidade_sha256'),'ambiente':{'gpu':'registrada_por_resposta'}})
            exigir(isinstance(inf.get('geracao'),dict) and isinstance(inf.get('implementacao'),dict), 'Configuração de inferência ausente')
    if c.get('schema_versao') in ('3.0','4.0','5.0'):
        from pipeline.validation.policy import CHOICES
        v = c.get('validacao')
        exigir(isinstance(v,dict) and all(v.get(k) in choices for k,choices in CHOICES.items()), 'Política de validação inválida')
        exigir(isinstance(v.get('implementacao'),dict) and isinstance(v.get('ambientes'),list), 'Proveniência da validação ausente')
        exigir(bool(v['implementacao']) and all(isinstance(h,str) and re.fullmatch('[0-9a-f]{64}',h) for h in v['implementacao'].values()), 'Hashes de implementação inválidos')
        if v['politica_validacao'] in ('otimizada_v1','relacionada_v1','relacionada_v2'):
            exigir(isinstance(v.get('mapa_testes_sha256'),str) and re.fullmatch('[0-9a-f]{64}',v['mapa_testes_sha256']), 'Mapa de testes sem hash')
        if (c['schema_versao']=='4.0' or c['schema_versao']=='5.0' and c.get('contrato_validacao_versao')=='4.0'):
            exigir(v['politica_validacao']=='relacionada_v2' and isinstance(v.get('cobertura'),dict),'Contrato 4.0 sem cobertura')
            exigir(v['repeticao_api']=='ampla','Contrato v4 requer repetição integral')
            for k in ('revisao_sha256','mapa_sha256','conjunto_d_sha256'):
                exigir(isinstance(v['cobertura'].get(k),str) and re.fullmatch('[0-9a-f]{64}',v['cobertura'][k]),'Hash de cobertura inválido')
            exigir(v['cobertura']['mapa_sha256']==v['mapa_testes_sha256'],'Mapas de cobertura divergentes')
            exigir(v.get('baseline_sha256')==c.get('baseline_testes_sha256'),'Hash baseline de cobertura divergente')
        else:exigir(v['politica_validacao']!='relacionada_v2','relacionada_v2 requer contrato 4.0')
    exigir(c.get('modo') in ('real','dry-run','preflight'), 'Modo do contrato inválido')
    exigir(c.get('commit_alvo') == cat.commit and c.get('hashes_catalogo') == cat.hashes, 'Commit/hashes de catálogo divergentes')
    ids = c.get('casos'); all_ids = {i['caso_id'] for i in cat.casos}
    exigir(isinstance(ids,list) and all(isinstance(i,str) for i in ids) and len(set(ids)) == len(ids) and set(ids) <= all_ids, 'Casos do contrato inválidos')
    exigir(isinstance(c.get('estrategias'),list) and isinstance(c.get('diagnosticos'),list), 'Estratégias do contrato inválidas')
    exigir(all(e in ESTRATEGIAS for e in c['estrategias']) and all(e in DIAGNOSTICOS for e in c['diagnosticos']), 'Estratégias do contrato inválidas')
    exigir(len(set(c['estrategias']+c['diagnosticos'])) == len(c['estrategias']+c['diagnosticos']), 'Estratégias duplicadas')
    exigir(c.get('comparador') in ('blocos_unicos_v1', 'ocorrencias_contexto_v2'), 'Comparador incompatível')
    _perfil(entrada)
    if (c.get('schema_versao')=='4.0' or c.get('schema_versao')=='5.0' and c.get('contrato_validacao_versao')=='4.0'):_cobertura(entrada)


def carregar(raiz, execucao, catalogo_path):
    raiz = Path(raiz).resolve()
    exigir(raiz.is_dir(), 'Entrada ausente')
    # Confinar sidecars antes do loader existente.
    catalogo_path = Path(catalogo_path).resolve()
    for name in ('catalogo_meta.json','exclusoes.json'):
        if (catalogo_path.parent/name).exists(): relativo(catalogo_path.parent,name)
    cat = carregar_catalogo(catalogo_path)
    entrada = Entrada(raiz,execucao,cat,None,[],[],None)
    entrada.registrar(catalogo_path,'catalogo/catalogo_issues.json')
    for name in ('catalogo_meta.json','exclusoes.json'):
        if (catalogo_path.parent/name).exists():entrada.registrar(catalogo_path.parent/name,'catalogo/'+name)
    for role, source in cat.meta.get('fontes',{}).items():
        entrada.registrar(relativo(RAIZ_REPO,source['arquivo']),'catalogo/fontes/'+role)
    contract_path = raiz/'contrato_execucao.json'
    if cat.ampliado:
        contract_path = relativo(raiz,'contrato_execucao.json')
        entrada.contrato = ler_json(contract_path)
        entrada.registrar(contract_path,'contrato_execucao.json')
        _validar_contrato(entrada)
    else:
        exigir(not contract_path.exists(), 'Contrato ampliado com catálogo histórico')
        entrada.avisos.append({'tipo':'proveniencia_historica_limitada','motivo':'sem_contrato'})
    # O mapa D participa da normalização retrospectiva.
    d_path = RAIZ_REPO/'config/conjunto_d.json'
    if d_path.exists():
        entrada.registrar(d_path,'normalizacao/conjunto_d.json')
        from pipeline.validation.conjunto_d import _lista
        _lista.cache_clear()  # Não atribuir um mapa novo a inferências de um cache antigo.
    rows_path = raiz/'resultados_consolidados/execucoes.jsonl'
    preflight_mode = entrada.contrato and entrada.contrato['modo'] == 'preflight'
    if preflight_mode:
        pre_path = relativo(raiz,'preflight.json');pre = ler_json(pre_path)
        exigir(pre.get('status')=='concluido' and pre.get('contrato_execucao_sha256') == digest(contract_path), 'Preflight incompatível')
        exigir(pre.get('casos') == len(entrada.contrato['casos']) and pre.get('custo_api_usd') == 0, 'Contagem/custo do preflight divergente')
        expected = {(i,e) for i in entrada.contrato['casos'] for e in entrada.contrato['estrategias']+entrada.contrato['diagnosticos']}
        listed = pre.get('prompts');exigir(isinstance(listed,list), 'Prompts preflight inválidos')
        got = [(p.get('caso'),p.get('estrategia')) for p in listed]
        exigir(len(set(got)) == len(got) and set(got) == expected, 'Pares preflight divergentes')
        for p in listed:
            file = relativo(raiz,f'prompts/{p["caso"]}_{p["estrategia"]}.json')
            data = ler_json(file)
            messages = data.get('mensagens')
            exigir(isinstance(messages,list) and all(isinstance(m,dict) and set(m)=={'role','content'} and all(isinstance(v,str) for v in m.values()) for m in messages), 'Mensagens preflight inválidas')
            # O builder calcula o hash com role antes de content; JSON arquivado ordena chaves.
            raw = json.dumps([{'role':m['role'],'content':m['content']} for m in messages],ensure_ascii=False).encode('utf-8')
            import hashlib
            exigir(data.get('hash_prompt') == p.get('hash_prompt') == hashlib.sha256(raw).hexdigest(), 'Hash do prompt preflight inválido')
            exigir(estrategia(data) == p['estrategia'], 'Estratégia do prompt preflight divergente')
            entrada.registrar(file,f'prompts/{p["caso"]}_{p["estrategia"]}.json')
        entrada.preflight = pre;entrada.registrar(pre_path,'preflight.json')
    exigir(rows_path.exists() or preflight_mode, 'JSONL ausente numa execução de correções')
    rows = []
    if rows_path.exists():
        rows_path = relativo(raiz,'resultados_consolidados/execucoes.jsonl')
        entrada.registrar(rows_path,'resultados_consolidados/execucoes.jsonl')
        for number,line in enumerate(rows_path.read_text(encoding='utf-8').splitlines(),1):
            if not line.strip():continue
            try:row=json.loads(line,object_pairs_hook=_pares,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            except ValueError as exc:raise ValueError(f'JSONL corrompido na linha {number}') from exc
            exigir(isinstance(row,dict) and isinstance(row.get('execucao'),str), 'Registro sem execução')
            if row['execucao'] == execucao:rows.append(row)
    exigir(not preflight_mode or not rows, 'Preflight contém tentativas de correção')
    seen=set();pairs=set();catalog={c['caso_id']:c for c in cat.casos}
    for row in rows:
        tid=row.get('tentativa_id');cid=row.get('caso_id')
        exigir(isinstance(tid,str) and tid and tid not in seen, 'ID de tentativa duplicado/inválido');seen.add(tid)
        exigir(cid in catalog,'Caso ausente do catálogo');case=catalog[cid]
        e=estrategia(row);exigir((cid,e) not in pairs, 'Par caso/estratégia duplicado');pairs.add((cid,e))
        validar_valores(row)
        signature='assinatura_ocorrencia' if cat.ampliado else 'assinatura'
        exigir(row.get(signature)==case.get(signature) and row.get('arquivo')==case['arquivo'] and row.get('check_id')==case['check_id'] and row.get('linha')==case['linha_inicio'], 'Identidade de ocorrência divergente')
        if cat.ampliado:
            contract=entrada.contrato
            exigir(cid in contract['casos'] and e in contract['estrategias']+contract['diagnosticos'], 'Tentativa fora do contrato')
            exigir(row.get('contrato_execucao_sha256') == digest(contract_path) and row.get('commit_alvo') == cat.commit and row.get('hashes_catalogo') == cat.hashes and row.get('perfil_sha256') == contract['perfil_sha256'], 'Proveniência da tentativa divergente')
            simulated=bool(row.get('dry_run') or row.get('modelo')=='dry-run')
            exigir(simulated == (contract['modo']=='dry-run'), 'População divergente do modo contratado')
            exigir(all('F_'+d in row and isinstance(row.get('classificacao_'+d),str) for d in DEFS), 'Resultados científicos ampliados ausentes')
            for d in DEFS:
                if row.get(f'classificacao_{d}')=='aceita':
                    exigir(row.get('status_aplicacao')=='aplicado' and (row.get('R'),row.get(f'F_{d}'),row.get('M'))==(1,1,1), 'Aceite contraditório')
            exigir(row.get('classificacao_final') == row.get('classificacao_criterio'), 'Classificação principal divergente')
            if contract.get('schema_versao')=='5.0' and not row.get('dry_run'):
                exigir(row.get('identidade_inferencia')==contract['inferencia'] and row.get('provedor')==contract['inferencia']['provedor'], 'Inferência da tentativa diverge do contrato')
            ledger=row.get('artefatos_sha256');exigir(isinstance(ledger,dict) and bool(ledger),'Hashes de artefatos ausentes')
            for file, old in ledger.items():
                artifact=relativo(raiz,file)
                exigir(digest(artifact)==old,'Hash de artefato adulterado')
                entrada.registrar(artifact,'artefatos/'+file)
            # Cada referência declarada deve estar coberta pelo ledger, incluindo cópias portáteis.
            declared=row.get('artefatos');exigir(isinstance(declared,dict),'Referências de artefatos ausentes')
            if contract.get('schema_versao') in ('3.0','4.0','5.0') and row['status_aplicacao']=='aplicado':
                exigir(row.get('politica_validacao')==contract['validacao']['politica_validacao'], 'Política da tentativa diverge do contrato')
                cache=row.get('cache_validacao')
                exigir(isinstance(cache,dict) and set(cache)=={'sast','funcional'}, 'Proveniência de cache ausente')
                for componente,info in cache.items():
                    exigir(isinstance(info,dict) and type(info.get('hit')) is bool and
                           isinstance(info.get('chave'),str) and re.fullmatch('[0-9a-f]{64}',info['chave']), 'Cache de validação inválido')
                evidencia=declared.get('evidencia_funcional')
                exigir(isinstance(evidencia,str),'Evidência funcional portátil ausente')
                candidato=Path(evidencia)
                candidato=candidato if candidato.is_absolute() else RAIZ_REPO/candidato
                candidato=relativo(raiz,candidato.resolve().relative_to(raiz).as_posix())
                exigir(digest(candidato)==cache['funcional'].get('evidencia_sha256'),'Hash da evidência funcional divergente')
                if (contract['schema_versao']=='4.0' or contract['schema_versao']=='5.0' and contract.get('contrato_validacao_versao')=='4.0'):
                    functional=ler_json(candidato)
                    exigir(isinstance(row.get('cobertura_detalhada'),dict) and row['cobertura_detalhada']==functional.get('cobertura_detalhada'),
                           'Cobertura funcional divergente da evidência')
                    exigir(not functional.get('cobertura_insuficiente') or all(row.get('F_'+d)!=1 for d in DEFS),
                           'F positivo com cobertura insuficiente')
            for value in declared.values():
                exigir(isinstance(value,str), 'Referência de artefato inválida')
                candidates=[file for file in ledger if value==file or value.endswith('/'+file)]
                exigir(len(candidates)==1, 'Referência sem hash inequívoco')
        else:
            for role,value in row.get('artefatos',{}).items():
                # Caminhos antigos são relativos ao repositório.
                p=relativo(RAIZ_REPO,value,existe=False)
                if p.is_file():entrada.registrar(p,'historico/'+value)
                else:entrada.avisos.append({'tipo':'artefato_historico_ausente','tentativa_id':tid,'papel':role,'arquivo':value})
        normalized=normalizar_atual(row,case,e)
        entrada.linhas.append(normalized)
    sess_name=f'resultados_consolidados/{execucao}_sessoes.json'
    if (raiz/sess_name).exists():
        p=relativo(raiz,sess_name);sessions=ler_json(p)
        exigir(isinstance(sessions,list) and all(isinstance(s,dict) and s.get('execucao')==execucao for s in sessions),'Sessões incompatíveis')
        entrada.sessoes=sessions;entrada.registrar(p,sess_name)
    entrada.linhas.sort(key=lambda l:(l['caso_id'],('P1','P2','P3','P4','P1L').index(l['estrategia_curta'])))
    # Baseline e gate também são parte da rastreabilidade ampliada.
    if cat.ampliado:
        gate_path=relativo(raiz,'sast_antes/reproducao.json');raw=relativo(raiz,'sast_antes/baseline_raw.json')
        report=ler_json(gate_path)
        exigir(report.get('reproduzido') is True and report.get('contrato_execucao_sha256')==digest(contract_path) and report.get('baseline_sha256')==digest(raw), 'Baseline/gate incompatível')
        from collections import Counter
        baseline_data=ler_json(raw)
        exigir(baseline_data.get('version')==entrada.contrato['semgrep_versao'] and isinstance(baseline_data.get('results'),list), 'Schema/versão do baseline incompatível')
        expected=Counter((c['check_id'],c['arquivo'],c['linha_inicio'],c['coluna_inicio'],c['linha_fim'],c['coluna_fim']) for c in cat.casos)
        actual=Counter()
        for item in baseline_data['results']:
            file=item.get('path');p=Path(file) if isinstance(file,str) else Path('/')
            exigir(isinstance(file,str) and not p.is_absolute() and '..' not in p.parts, 'Caminho de baseline inválido')
            exigir(item.get('check_id') in entrada.perfil.dados['id_regras'],'Regra de baseline fora do perfil')
            if entrada.perfil.no_escopo(file):
                start,end=item.get('start',{}),item.get('end',{})
                coords=[start.get('line'),start.get('col'),end.get('line'),end.get('col')]
                exigir(all(type(n) is int and n>0 for n in coords),'Coordenadas de baseline inválidas')
                actual[(item['check_id'],file,*coords)]+=1
        exigir(actual==expected,'Baseline não corresponde ao catálogo')
        entrada.registrar(gate_path,'sast_antes/reproducao.json');entrada.registrar(raw,'sast_antes/baseline_raw.json')
    entrada.revalidar()
    return entrada
