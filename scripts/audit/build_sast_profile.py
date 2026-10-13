#!/usr/bin/env python3
"""Congela YAMLs locais e remotos previamente exportados em um perfil verificável."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa
import argparse
import hashlib
import json
import tempfile
import shutil
import yaml
from pipeline.caminhos import RAIZ_REPO
from pipeline.catalogo import exigir, digest
from scripts.experiment.build_expanded_catalog import publicar, serializar


def construir(remote: Path, local: Path, exclusions: Path):
    arquivos = sorted(local.rglob('*.yaml'))
    remote_raw = yaml.safe_load(remote.read_text())
    remotas = remote_raw.get('rules')
    exigir(isinstance(remotas,list) and remotas, 'Exportação remota sem regras')
    locais = [r for p in arquivos for r in yaml.safe_load(p.read_text())['rules']]
    ids = [r.get('id') for r in remotas+locais]
    exigir(all(isinstance(i,str) and i for i in ids) and len(ids)==len(set(ids)), 'IDs de regras inválidos/duplicados')
    scope = [l.strip() for l in exclusions.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
    scope = sorted(set(scope + ['.npmrc','frontend/.npmrc']))
    artifacts = {}
    for name,rules in (('regras_remotas.yaml',remotas),('regras_locais.yaml',locais)):
        artifacts[name] = yaml.safe_dump({'rules':sorted(rules,key=lambda r:r['id'])},allow_unicode=True,sort_keys=True,width=100000).encode()
    meta = {'schema_versao':'1.0','perfil_id':'ampliado_v1','semgrep_versao':'1.177.0',
            'configs':[{'arquivo':name,'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in artifacts.items()],
            'origem_remota':'p/default','exportacao_sha256':digest(remote),'exportacao_obtida_depois_auditoria':True,
            'id_regras':sorted(ids),'timeout_regra_s':30,'timeout_processo_s':900,'escopo':scope,
            'escopo_sha256':hashlib.sha256(json.dumps(scope,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
            'exclusoes_origem_sha256':digest(exclusions),
            'regras_locais_origem':{p.relative_to(local).as_posix():digest(p) for p in arquivos},
            'flags':{'metrics':'off','rewrite_rule_ids':False,'use_git_ignore':True}}
    artifacts['perfil.json']=serializar(meta)
    return artifacts


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--regras-remotas',type=Path,required=True)
    ap.add_argument('--regras-locais',type=Path,default=RAIZ_REPO/'rules')
    ap.add_argument('--saida',type=Path,required=True)
    a=ap.parse_args()
    try:
        artifacts=construir(a.regras_remotas,a.regras_locais,RAIZ_REPO/'config/semgrepignore')
        publicar(a.saida,artifacts,lambda:None)
    except (ValueError,OSError,KeyError,yaml.YAMLError) as exc:
        ap.exit(1,f'ERRO: {exc}\n')
    print(f'Perfil congelado: {a.saida}')


if __name__=='__main__':main()
