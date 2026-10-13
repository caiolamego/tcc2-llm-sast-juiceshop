"""Preflight, contrato e contexto do modo ampliado; sem alterar o fluxo legado."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import re

from pipeline.caminhos import RAIZ_REPO
from pipeline.catalogo import carregar, digest, exigir
from pipeline.sast.perfil import carregar as carregar_perfil
from pipeline.sast.semgrep_client import scan_perfil, carregar_scan_perfil, conferir_versao
from pipeline.sast.comparacao import gate, VERSAO
from pipeline.prompts import builder
from pipeline.registro import ler_execucoes
from pipeline.target.workspace import PoolWorktrees


def salvar(path: Path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n')


def head(path):
    import subprocess
    return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()


def limpo(path):
    import subprocess
    return not subprocess.check_output(['git','-C',str(path),'status','--porcelain','--untracked-files=all'],text=True).strip()


@dataclass
class Preparacao:
    catalogo: object
    perfil: object
    scan: object
    contrato_hash: str
    baseline_testes: Path
    saida: Path


def contrato(args, catalogo, perfil, casos):
    templates = [builder.ARQ_ROTEIRO, Path(builder.__file__), RAIZ_REPO/'src/pipeline/validation/runner.py']
    baseline=Path(args.baseline_testes).resolve()
    return {'schema_versao':'1.0','execucao':args.execucao,
            'modo':'preflight' if args.somente_preflight else 'dry-run' if args.dry_run else 'real',
            'commit_alvo':catalogo.commit,'hashes_catalogo':catalogo.hashes,'perfil_sha256':perfil.hash,
            'semgrep_versao':perfil.dados['semgrep_versao'],'estrategias':args.estrategias,
            'diagnosticos':args.diagnosticos,'casos':sorted(c['caso_id'] for c in casos),
            'comparador':VERSAO,'prompts_validacao_sha256':{p.name:digest(p) for p in templates},
            'baseline_testes_sha256':None if args.somente_preflight else digest(baseline)}


def conferir_linhas(path, expected):
    if not path.exists(): return
    vistos = set()
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        try:
            line = json.loads(raw)
        except ValueError as exc:
            raise ValueError(f'Registro incompleto/corrompido na linha {number}; não será retomado silenciosamente') from exc
        exigir(line.get('contrato_execucao_sha256')==expected,'Tentativa sem contrato compatível na saída')
        exigir(line.get('commit_alvo'), 'Tentativa sem commit')
        tid = line.get('tentativa_id')
        exigir(isinstance(tid, str) and tid and tid not in vistos, 'ID de tentativa inválido/duplicado')
        vistos.add(tid)
        exigir(isinstance(line.get('artefatos_sha256'), dict), 'Tentativa sem hashes dos artefatos')
        for file, old in line['artefatos_sha256'].items():
            relative = Path(file)
            exigir(not relative.is_absolute() and '..' not in relative.parts, 'Caminho de artefato inválido')
            exigir(digest(path.parents[1]/relative)==old, f'Artefato de tentativa alterado: {file}')


def preparar(args, catalogo, casos):
    exigir(args.perfil_sast and args.saida,'Catálogo ampliado requer --perfil-sast e --saida')
    exigir(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',args.execucao), 'ID de execução inválido')
    exigir(args.k>=1,'K deve ser positivo')
    perfil=carregar_perfil(Path(args.perfil_sast))
    exigir(catalogo.meta['semgrep_versao']==perfil.dados['semgrep_versao'],'Versão catálogo/perfil divergente')
    conferir_versao(args.semgrep_bin, perfil)
    exigir({c['check_id'] for c in catalogo.casos}<=set(perfil.dados['id_regras']),'Regra do catálogo ausente no perfil')
    exigir(all(perfil.no_escopo(c['arquivo']) for c in catalogo.casos),'Perfil exclui caso do catálogo')
    from dotenv import dotenv_values
    expected=os.environ.get('JUICESHOP_COMMIT') or dotenv_values(RAIZ_REPO/'.env').get('JUICESHOP_COMMIT')
    exigir(not expected or expected==catalogo.commit,'Commit do ambiente divergente do catálogo')
    worktrees=[RAIZ_REPO/f'workspace/wt-{i}' for i in range(1,args.k+1)]
    for wt in worktrees:
        exigir(wt.is_dir() and head(wt)==catalogo.commit,'Worktree ausente ou em commit diferente')
        exigir(limpo(wt),'Worktree modificado; não será restaurado no preflight')
        for file, old in catalogo.meta['arquivos_fonte'].items():
            file_path=(wt/file).resolve()
            exigir(file_path.is_relative_to(wt.resolve()) and digest(file_path)==old,f'Fonte do catálogo divergente: {file}')
    saida=Path(args.saida).resolve()
    exigir(saida!=RAIZ_REPO/'outputs' and saida!=RAIZ_REPO and not saida.is_relative_to(RAIZ_REPO/'workspace'), 'Saída inválida para execução ampliada')
    # Diretórios históricos não podem ser usados como saída de execução.
    for protected in ('sast_antes','resultados_consolidados','catalogos','auditoria_sast'):
        exigir(not saida.is_relative_to(RAIZ_REPO/'outputs'/protected),'Saída sobreposta a evidências históricas')
    contract_path=saida/'contrato_execucao.json'
    current=contrato(args,catalogo,perfil,casos)
    if saida.exists() and not contract_path.exists():
        exigir(not any(saida.iterdir()),'Saída existente sem contrato de execução')
    saida.mkdir(parents=True,exist_ok=True)
    if contract_path.exists():
        exigir(json.loads(contract_path.read_text())==current,'Contrato incompatível; use nova execução/saída')
    else:salvar(contract_path,current)
    contract_hash=digest(contract_path)
    conferir_linhas(saida/'resultados_consolidados/execucoes.jsonl',contract_hash)
    baseline=saida/'sast_antes/baseline_raw.json'
    gate_file=saida/'sast_antes/reproducao.json'
    if baseline.exists():
        exigir(gate_file.exists(),'Baseline sem relatório de proveniência')
        old=json.loads(gate_file.read_text())
        exigir(old.get('contrato_execucao_sha256')==contract_hash and old.get('baseline_sha256')==digest(baseline),'Baseline alterado/incompatível')
        scan=carregar_scan_perfil(baseline,worktrees[0],perfil)
    else:
        scan=scan_perfil(worktrees[0],perfil,baseline,args.semgrep_bin)
    report=gate(catalogo,scan)
    report.update(contrato_execucao_sha256=contract_hash,baseline_sha256=digest(baseline) if baseline.exists() else None)
    salvar(gate_file,report)
    exigir(report['reproduzido'],f'Perfil não reproduz catálogo; veja {gate_file}')
    if args.somente_preflight:
        prompts=[]
        for issue in casos:
            for e in args.estrategias+args.diagnosticos:
                prompt=builder.montar(issue,worktrees[0],e)
                path=saida/'prompts'/f'{issue["caso_id"]}_{e}.json'
                data=prompt.to_dict()
                if path.exists():exigir(json.loads(path.read_text())==data,'Prompt preflight alterado')
                else:salvar(path,data)
                prompts.append({'caso':issue['caso_id'],'estrategia':e,'hash_prompt':prompt.hash_prompt})
        salvar(saida/'preflight.json',{'status':'concluido','casos':len(casos),'prompts':prompts,
                'contrato_execucao_sha256':contract_hash,'custo_api_usd':0,'diagnosticos':scan.diagnosticos,
                'cobertura_funcional':'não executada'})
        return None
    return Preparacao(catalogo,perfil,scan,contract_hash,Path(args.baseline_testes).resolve(),saida)


def sondar(args, catalogo):
    """Sondagem manual com o mesmo gate/perfil/comparador, separada das métricas."""
    import subprocess
    from pipeline.sast.comparacao import comparar, chave_caso
    from pipeline.validation.runner import validar, ConfigValidacao
    args.execucao = args.rotulo
    args.estrategias, args.diagnosticos = ['P1'], []
    args.k, args.somente_preflight, args.dry_run = 1, False, True
    issue = next((c for c in catalogo.casos if c['caso_id'] == args.caso), None)
    exigir(issue is not None, 'Caso ausente do catálogo')
    patch = Path(args.patch).resolve()
    prep = preparar(args, catalogo, [issue])
    result_path = prep.saida / 'sondagem.json'
    exigir(not result_path.exists(), 'Sondagem já concluída; use outra saída')
    with PoolWorktrees(RAIZ_REPO/'workspace',1,catalogo.commit).alugar() as wt:
        # A sondagem pode alterar outros arquivos: capturar somente os caminhos do diff, validados.
        names = subprocess.check_output(['git','apply','--numstat',str(patch)],cwd=wt,text=True)
        files = [line.split('\t',2)[2] for line in names.splitlines()]
        before = {}
        for file in files:
            path = (wt/file).resolve()
            exigir(path.is_relative_to(wt.resolve()) and path.is_file() and prep.perfil.no_escopo(file), 'Patch fora do escopo ou cria/remove arquivo')
            before[file] = path.read_bytes()
        subprocess.run(['git','apply',str(patch)],cwd=wt,check=True,timeout=60)
        after = scan_perfil(wt,prep.perfil,prep.saida/'sast_depois/sondagem_raw.json',args.semgrep_bin)
        comp = comparar(prep.scan,after,chave_caso(issue),{f:(raw,(wt/f).read_bytes()) for f,raw in before.items()})
        data = {'aviso':'Sondagem não integra métricas de geração LLM','origem_patch':args.origem,
                'caso_id':issue['caso_id'],'patch_sha256':digest(patch),
                'contrato_execucao_sha256':prep.contrato_hash,'comparacao':comp}
        if args.validar:
            data['validacao'] = validar(wt,files,ConfigValidacao(arquivo_linha_de_base=prep.baseline_testes)).to_dict()
        salvar(result_path,data)
    print(f'Sondagem arquivada em {result_path}')
