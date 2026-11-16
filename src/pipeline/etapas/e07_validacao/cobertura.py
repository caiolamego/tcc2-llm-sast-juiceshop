"""Revisão funcional por ocorrência e seleção v2; sem execução de serviços."""
from collections import defaultdict
from pathlib import Path
import json
import subprocess
import re
import yaml

from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.comum.identidade import digest, hash_json
from pipeline.etapas.e07_validacao.selecao import YAMLUnico, interno

DOMINIOS = {'servidor', 'api', 'frontend'}


def ler_yaml(path):
    try:
        data = yaml.load(Path(path).read_text(encoding='utf-8'), Loader=YAMLUnico)
    except yaml.YAMLError as exc:
        raise ValueError('YAML de cobertura inválido') from exc
    if not isinstance(data, dict):
        raise ValueError('Documento de cobertura deve ser objeto')
    return data


def carregar(revisao, mapa, wt, catalogo=None, permitir_avaliadores_alterados=False):
    revisao, mapa, wt = Path(revisao).resolve(), Path(mapa).resolve(), Path(wt).resolve()
    data, mapping = ler_yaml(revisao), ler_yaml(mapa)
    if data.get('schema_versao') != '1.0' or mapping.get('schema_versao') != '2.0':
        raise ValueError('Schema de cobertura/mapa incompatível')
    if mapping.get('cobertura_sha256') != digest(revisao):
        raise ValueError('Mapa divergente da revisão funcional')
    if catalogo and (data.get('commit_alvo') != catalogo.commit or data.get('hashes_catalogo') != catalogo.hashes):
        raise ValueError('Revisão divergente do catálogo')
    groups, cases = data.get('grupos'), data.get('casos')
    if not isinstance(groups, dict) or not isinstance(cases, list):
        raise ValueError('Grupos/casos de cobertura ausentes')
    seen = set(); expected = {c['caso_id']: c for c in catalogo.casos} if catalogo else None
    all_tests=set()
    for cid, group in groups.items():
        if not isinstance(cid,str) or not cid or not isinstance(group,dict) or group.get('dominio') not in DOMINIOS:
            raise ValueError('Grupo/domínio inválido')
        if not group.get('comportamentos') or not group.get('obrigatorios'):
            raise ValueError('Grupo sem comportamentos/asserções obrigatórias')
        compilacoes=group.get('compilacoes')
        if not isinstance(compilacoes,list) or not compilacoes or len(set(compilacoes))!=len(compilacoes) or set(compilacoes)-{'servidor','frontend'}:
            raise ValueError('Compilação de domínio inválida')
        if ('frontend' if group['dominio']=='frontend' else 'servidor') not in compilacoes:
            raise ValueError('Compilação não cobre o domínio')
        tests = group.get('testes')
        if not isinstance(tests,list) or not tests:
            raise ValueError('Grupo sem seleção de testes')
        names = set()
        for test in tests:
            name, origin = test.get('arquivo'),test.get('origem')
            if name in names or origin not in ('alvo','avaliacao'):
                raise ValueError('Origem/teste duplicado ou inválido')
            names.add(name)
            if (origin,name) in all_tests:
                raise ValueError('Teste repetido entre grupos; publicar um grupo compartilhado')
            all_tests.add((origin,name))
            path=interno(wt if origin=='alvo' else RAIZ_REPO,name)
            if (not path.is_file() and not (origin=='alvo' and permitir_avaliadores_alterados)) or not isinstance(test.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',test['sha256']):
                raise ValueError('Teste ausente ou sem hash')
            if origin=='avaliacao':
                if not name.startswith('tests/functional/juice_shop/') or digest(path)!=test['sha256']:
                    raise ValueError('Avaliação adicional adulterada')
                destination=interno(wt,test.get('destino'))
                if destination.exists():
                    raise ValueError('Destino de avaliação já ocupado')
            relative=test.get('destino',name)
            prefix={'api':'test/api/','servidor':'test/server/','frontend':'frontend/src/'}[group['dominio']]
            suffix='.unit.test.ts' if group['dominio']=='servidor' else '.test.ts' if group['dominio']=='api' else '.spec.ts'
            if not relative.startswith(prefix) or not relative.endswith(suffix):raise ValueError('Teste incompatível com domínio')
        for obligation in group['obrigatorios']:
            if not isinstance(obligation,dict) or obligation.get('arquivo') not in names or not obligation.get('nome'):
                raise ValueError('Asserção obrigatória sem teste associado')
    for case in cases:
        cid=case.get('caso_id');file=case.get('arquivo')
        if not isinstance(cid,str) or cid in seen or case.get('revisao') not in ('pendente','adequada','insuficiente'):
            raise ValueError('Caso/revisão inválida ou duplicada')
        seen.add(cid);interno(wt,file)
        if expected and (cid not in expected or any(case.get(k)!=expected[cid].get(k) for k in ('arquivo','check_id'))):
            raise ValueError('Identidade da ocorrência divergente')
        if not case.get('funcionalidade') or not case.get('justificativa') or not case.get('evidencia_codigo'):
            raise ValueError('Revisão sem justificativa/evidência')
        if any(g not in groups for g in case.get('grupos',[])):
            raise ValueError('Grupo desconhecido')
        if case['revisao']=='adequada' and not case.get('grupos'):
            raise ValueError('Adequação sem testes')
        if case['revisao']!='adequada' and not case.get('lacunas'):
            raise ValueError('Lacuna sem explicação')
    if expected and seen != set(expected):
        raise ValueError('Revisão não reconcilia todos os casos')
    derived=derivar_mapa(data,digest(revisao))
    if mapping != derived:
        raise ValueError('Mapa não corresponde à união da revisão')
    d=data.get('conjunto_d',{})
    dp=interno(RAIZ_REPO,d.get('arquivo'))
    if not dp.is_file() or digest(dp)!=d.get('sha256'):
        raise ValueError('Conjunto D divergente')
    return data


def derivar_mapa(data, sha):
    files=defaultdict(set)
    for case in data['casos']:
        files[case['arquivo']].update(case.get('grupos',[]))
    return {'schema_versao':'2.0','cobertura_sha256':sha,
            'arquivos':{f:{'grupos':sorted(gs)} for f,gs in sorted(files.items())}}


def selecionar(data, arquivos, wt):
    files=sorted(set(arquivos)); groups=set(); reasons=[]
    if not files: reasons.append('sem arquivos alterados/selecionados')
    for file in files:
        interno(Path(wt),file)
        cases=[c for c in data['casos'] if c['arquivo']==file]
        if not cases: reasons.append(file+': arquivo sem revisão')
        for case in cases:
            groups.update(case.get('grupos',[]))
            if case['revisao']!='adequada': reasons.append(case['caso_id']+': '+case['justificativa'])
    for gid in sorted(groups):
        for test in data['grupos'][gid]['testes']:
            if test['origem']=='alvo':
                path=interno(Path(wt),test['arquivo'])
                if not path.is_file() or digest(path)!=test['sha256']:reasons.append(test['arquivo']+': avaliador alterado/ausente')
    if not groups: reasons.append('seleção de testes vazia')
    return {'arquivos':files,'grupos':sorted(groups),'dominios':sorted({data['grupos'][g]['dominio'] for g in groups}),
            'motivos':sorted(set(reasons)),'suficiente':not reasons}


def ambiente(wt, frontend=False):
    from pipeline.comum.identidade import ambiente as legado, dependencias, versao
    value=legado(wt)
    from pipeline.etapas.e07_validacao.preparacao_api import inventario
    value['preparacao_api']=inventario(wt)
    if frontend:
        base=Path(wt)/'frontend'
        value['frontend']={'lock_sha256':digest(base/'package-lock.json'),
                           'instalacao_lock_sha256':digest(base/'node_modules/.package-lock.json'),
                           'dependencias_sha256':dependencias(base/'node_modules')}
    return value


def identidade(data, revisao, mapa):
    files={str(Path(revisao).resolve()):digest(revisao),str(Path(mapa).resolve()):digest(mapa)}
    d=interno(RAIZ_REPO,data['conjunto_d']['arquivo']);files[str(d)]=digest(d)
    for g in data['grupos'].values():
        for t in g['testes']:
            if t['origem']=='avaliacao':
                p=interno(RAIZ_REPO,t['arquivo']);files[str(p)]=digest(p)
    return {'revisao_sha256':digest(revisao),'mapa_sha256':digest(mapa),
            'conjunto_d_sha256':digest(d),'testes_adicionais':{Path(p).relative_to(RAIZ_REPO).as_posix():h for p,h in files.items()
                                                             if Path(p).is_relative_to(RAIZ_REPO/'tests')},
            'adaptadores_sha256':{p.name:digest(p) for p in (Path(__file__),Path(__file__).with_name('execucao_cobertura.py'),Path(__file__).with_name('conjunto_d.py'),Path(__file__).with_name('preparacao_api.py'),Path(__file__).with_name('preparo_api_cobertura.mjs'))},
            'falhas_operacionais':'grupo_invalido_nao_mede_f_v1','selecao':'uniao_por_arquivo_v2','execucao':{'TSX_DISABLE_CACHE':'1','frontend_CI':'true','frontend_watch':False}}


def validar_baseline(path, data, revisao, mapa, wt, selection, conferir_ambiente=True, exigir_grupos=True):
    baseline=json.loads(Path(path).read_text(encoding='utf-8'))
    if (baseline.get('schema_versao')!='2.0' or baseline.get('status')!='concluido' or baseline.get('commit_alvo')!=data['commit_alvo'] or
            baseline.get('cobertura')!=identidade(data,revisao,mapa)):
        raise ValueError('Baseline funcional incompatível')
    for name,h in baseline.get('artefatos_sha256',{}).items():
        if digest(interno(Path(path).resolve().parent,name))!=h:raise ValueError('Evidência de baseline alterada')
    if conferir_ambiente:
        if 'api' in selection['dominios']:
            from pipeline.etapas.e07_validacao.preparacao_api import conferir
            conferir(wt)
        current=ambiente(Path(wt),'frontend' in selection['dominios']);current.pop('porta_api',None)
        expected=dict(baseline.get('ambiente',{}))
        if 'frontend' not in selection['dominios']:expected.pop('frontend',None)
        if 'api' not in selection['dominios']:
            expected.pop('preparacao_api',None);current.pop('preparacao_api',None)
        if current!=expected:
            raise ValueError('Ambiente funcional diverge do baseline')
    for gid in selection['grupos']:
        g=baseline.get('grupos',{}).get(gid,{})
        if exigir_grupos and (g.get('comparavel') is not True or not g.get('executados') or not g.get('obrigatorios_aprovados')):
            raise ValueError('Grupo sem baseline comparável: '+gid)
        if exigir_grupos:
            for domain in data['grupos'][gid]['compilacoes']:
                if baseline.get('compilacoes',{}).get(domain,{}).get('passou') is not True:
                    raise ValueError('Compilação baseline sem aprovação: '+domain)
    return baseline
