#!/usr/bin/env python3
"""Aplica juntos os patches aceitos de uma execução e gera a evidência da RRIS.

Roda dentro do Docker, com a trava das worktrees, sem LLM. Nada aqui escreve na
execução avaliada: a evidência vai para uma pasta nova, lida depois por
scripts/relatorios/consolidar_metricas.py --evidencia-rris.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
import argparse
import hashlib
import json
import shutil
import subprocess
import threading

from pipeline.comum.caminhos import RAIZ_REPO


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def salvar(path, data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def selecionar(linhas, definicao='criterio'):
    """Primeiro aceite de cada caso, na ordem em que as tentativas começaram."""
    aceitas=[r for r in linhas if r['condicao']=='desenho' and not r['dry_run'] and not r['pos_aceite']
             and r['status_aplicacao']=='aplicado' and (r.get('R'),r.get('F_'+definicao),r.get('M'))==(1,1,1)]
    return sorted(aceitas,key=lambda r:(str(r.get('original',{}).get('inicio_tentativa','')),r['tentativa_id']))


def patch_da_tentativa(raiz, linha):
    """Localiza o patch e confere com o hash registrado na tentativa."""
    path=Path(raiz)/'patches'/(linha['tentativa_id']+'.diff')
    if not path.is_file():
        raise ValueError('Patch ausente: '+linha['tentativa_id'])
    registrado=linha['original'].get('artefatos_sha256',{}).get(path.name)
    if registrado!=digest(path):
        raise ValueError('Patch diverge do registrado: '+linha['tentativa_id'])
    return path


def aplicar_em_ordem(wt, itens):
    """Aplica cada patch sobre os anteriores; conflito não interrompe os demais."""
    aplicados,conflitos=[],[]
    for tentativa,patch in itens:
        check=subprocess.run(['git','apply','--check',str(patch)],cwd=wt,capture_output=True,text=True)
        if check.returncode:
            conflitos.append({'tentativa_id':tentativa,'motivo':check.stderr.strip()[:400]})
            continue
        subprocess.run(['git','apply',str(patch)],cwd=wt,check=True,capture_output=True,text=True)
        aplicados.append(tentativa)
    return aplicados,conflitos


def classificador_conjunto(original, casos):
    """Um teste ligado a qualquer caso do conjunto é D na validação conjunta."""
    def classificar(testes, arquivo=None, caso=None):
        partes=[original(testes,arquivo,c) for c in casos] or [original(testes,arquivo)]
        d_criterio=sorted({t for p in partes for t in p['d_criterio']})
        d_marcador=sorted({t for p in partes for t in p['d_marcador']})
        return {'d_marcador':d_marcador,'d_criterio':d_criterio,
                'f_marcador':sorted(set(testes)-set(d_marcador)),'f_criterio':sorted(set(testes)-set(d_criterio))}
    return classificar


def validar_conjunto(wt, arquivos, casos, args):
    from pipeline.etapas.e07_validacao import conjunto_d
    from pipeline.etapas.e07_validacao.camadas import ConfigValidacao, validar
    cfg=ConfigValidacao(lock_t4=threading.Lock(),arquivo_linha_de_base=args.baseline_testes,politica='relacionada_v2',
                        mapa=args.mapa_testes,repeticao_api='ampla')
    cfg.cobertura=args.cobertura_funcional
    original=conjunto_d.classificar
    conjunto_d.classificar=classificador_conjunto(original,casos)
    try:
        r=validar(wt,sorted(arquivos),cfg)
    finally:
        conjunto_d.classificar=original
    return {'passou':r.F_criterio is True,'F_criterio':r.F_criterio,'F_sem_separacao':r.F_sem_separacao,
            'arquivos':sorted(arquivos),'casos':sorted(casos),'testes_falhos_f_criterio':r.testes_falhos_f_criterio,
            'testes_falhos_d_criterio':r.testes_falhos_d_criterio,'cobertura':r.cobertura_detalhada}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--entrada',type=Path,required=True,help='Pasta da execução real')
    ap.add_argument('--execucao',required=True)
    ap.add_argument('--saida',type=Path,required=True)
    ap.add_argument('--catalogo',type=Path,default=RAIZ_REPO/'outputs/catalogos/ampliado_v1/catalogo_issues.json')
    ap.add_argument('--perfil-sast',type=Path,default=RAIZ_REPO/'config/perfis/ampliado_piloto_v1/perfil.json')
    ap.add_argument('--baseline-testes',type=Path,required=True)
    ap.add_argument('--mapa-testes',type=Path,default=RAIZ_REPO/'config/mapa_testes_relacionados_v9.yaml')
    ap.add_argument('--cobertura-funcional',type=Path,default=RAIZ_REPO/'config/cobertura_funcional_v8.yaml')
    ap.add_argument('--semgrep-bin',default='.venv/bin/semgrep')
    args=ap.parse_args()
    try:
        from pipeline.etapas.e01_analise_sast.perfil import carregar as carregar_perfil
        from pipeline.etapas.e01_analise_sast.semgrep import scan_perfil
        from pipeline.etapas.e06_aplicacao.worktrees import PoolWorktrees
        from pipeline.etapas.e09_metricas.calculo import calcular
        from pipeline.etapas.e09_metricas.leitura import carregar
        args.saida.mkdir(parents=True,exist_ok=False)
        entrada=carregar(args.entrada,args.execucao,args.catalogo);calcular(entrada)
        if digest(args.perfil_sast)!=entrada.contrato['perfil_sha256']:
            raise ValueError('Perfil diferente do contrato da execução')
        selecionadas=selecionar(entrada.linhas)
        if not selecionadas:
            raise ValueError('Execução sem patches aceitos')
        itens=[(r['tentativa_id'],patch_da_tentativa(args.entrada,r)) for r in selecionadas]
        por_id={r['tentativa_id']:r for r in selecionadas}
        (args.saida/'patches').mkdir()
        shutil.copytree(args.perfil_sast.parent,args.saida/'perfil')
        perfil=carregar_perfil(args.saida/'perfil'/args.perfil_sast.name)
        pool=PoolWorktrees(RAIZ_REPO/'workspace',k=1,commit_esperado=entrada.catalogo.commit)
        with pool.alugar() as wt:
            antes=scan_perfil(wt,perfil,args.saida/'scan_antes.json',args.semgrep_bin)
            aplicados,conflitos=aplicar_em_ordem(wt,itens)
            arquivos={a for t in aplicados for a in por_id[t].get('arquivos_alterados',[])}
            casos=[por_id[t]['caso_id'] for t in aplicados]
            funcional=validar_conjunto(wt,arquivos,casos,args)
            depois=scan_perfil(wt,perfil,args.saida/'scan_depois.json',args.semgrep_bin)
        salvar(args.saida/'validacao_funcional.json',funcional)
        patches=[]
        for tentativa,patch in itens:
            if tentativa in aplicados:
                shutil.copy(patch,args.saida/'patches'/patch.name)
                patches.append({'tentativa_id':tentativa,'arquivo':'patches/'+patch.name,'sha256':digest(patch)})
        manifesto={'schema_versao':'1.0','execucao':args.execucao,'commit_baseline':entrada.catalogo.commit,
            'hashes_catalogo':entrada.catalogo.hashes,'perfil_sha256':entrada.contrato['perfil_sha256'],'definicao_f':'criterio',
            'patches':patches,'ordem_aplicacao':aplicados,'conflitos':conflitos,'nao_aplicadas':[c['tentativa_id'] for c in conflitos],
            'falhas_scan':{'antes':antes.falha_operacional,'depois':depois.falha_operacional}}
        for chave,nome in (('perfil','perfil/'+args.perfil_sast.name),('scan_antes','scan_antes.json'),('scan_depois','scan_depois.json'),
                           ('validacao_funcional','validacao_funcional.json')):
            manifesto[chave]={'arquivo':nome,'sha256':digest(args.saida/nome)}
        salvar(args.saida/'manifesto.json',manifesto)
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:
        ap.exit(1,f'ERRO: {exc}\n')
    print(f'{len(aplicados)} patches aplicados, {len(conflitos)} em conflito | funcional: {funcional["passou"]} | achados: {len(antes.findings)} -> {len(depois.findings)}')


if __name__=='__main__':raise SystemExit(main())
