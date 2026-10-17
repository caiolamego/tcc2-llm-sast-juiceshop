#!/usr/bin/env python3
"""Recompara evidências arquivadas com v1/v2; não executa scans, alvo ou LLM."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile

from pipeline.caminhos import RAIZ_REPO as ROOT
from pipeline.catalogo import carregar as carregar_catalogo
from pipeline.sast.associacoes import carregar as carregar_revisoes
from pipeline.sast.comparacao import comparar as v1, chave_caso
from pipeline.sast.comparacao_v2 import comparar as v2, VERSAO
from pipeline.sast.estrutura import identidade
from pipeline.sast.perfil import carregar as carregar_perfil
from pipeline.sast.semgrep_client import carregar_scan_perfil
from pipeline.validation.components import componentes


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(root, nome):
    path = (Path(root)/nome).resolve()
    if not path.is_relative_to(Path(root).resolve()) or not path.is_file():
        raise ValueError('Arquivo externo/ausente: '+str(nome))
    return path


def conferir_patch(original, corrected, patch):
    """Confere os hunks em memória, sem aplicar patches em um checkout."""
    lines = original.decode('utf-8').splitlines(keepends=True)
    output, cursor, old_count, new_count = [], 0, None, None
    files = 0
    for line in patch.decode('utf-8').splitlines(keepends=True):
        if line.startswith('diff --git '):
            files += 1
            continue
        match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        if match:
            if old_count not in (None,0) or new_count not in (None,0):
                raise ValueError('Hunk incompleto')
            start = int(match[1])-1 if int(match[2] or 1) else int(match[1])
            if start < cursor:
                raise ValueError('Hunks sobrepostos')
            output.extend(lines[cursor:start]);cursor=start
            if int(match[3])-1 != len(output) and int(match[4] or 1):
                raise ValueError('Coordenada posterior inconsistente')
            old_count, new_count = int(match[2] or 1), int(match[4] or 1)
        elif old_count is not None and (old_count or new_count):
            if line[:1] in (' ', '-'):
                if cursor >= len(lines) or lines[cursor] != line[1:]:
                    raise ValueError('Patch não corresponde ao fonte original')
                cursor += 1;old_count -= 1
            if line[:1] in (' ', '+'):
                output.append(line[1:]);new_count -= 1
            if line[:1] not in (' ', '+', '-') or min(old_count,new_count) < 0:
                raise ValueError('Hunk inválido/sem suporte')
    output.extend(lines[cursor:])
    if files != 1 or old_count != 0 or new_count != 0 or ''.join(output).encode() != corrected:
        raise ValueError('Fonte corrigido diverge do patch ou diff não é de arquivo único')


def executar(args):
    cat = carregar_catalogo(args.catalogo)
    cases = {c['caso_id']:c for c in cat.casos}
    profile = carregar_perfil(args.perfil_sast)
    revisions = carregar_revisoes(args.revisoes,args.catalogo,cat.casos,ROOT)
    inputs = {}
    def remember(path, expected=None):
        path = local(ROOT, Path(path).resolve())
        actual = sha(path)
        if expected is not None and actual != expected:
            raise ValueError('Hash divergente: '+str(path))
        inputs[path] = actual
        return path
    remember(args.catalogo);remember(args.revisoes)
    for path in (profile.caminho, *profile.configs):remember(path)
    parser_id = identidade(args.parser_checkout)
    remember(Path(args.parser_checkout)/'node_modules/typescript/lib/typescript.js')
    remember(__file__)
    for name,h in componentes().items():remember(ROOT/name,h)
    jobs = []
    if args.referencias:
        base = args.referencias.resolve()
        manifest = json.loads(remember(base/'manifesto.json').read_text())
        if manifest.get('status') != 'concluido' or manifest.get('commit_alvo') != cat.commit or manifest.get('perfil_sha256') != profile.hash:
            raise ValueError('Referências sem proveniência compatível')
        for name,h in manifest['fontes_sha256'].items():remember(name,h)
        for name,h in manifest['artefatos_sha256'].items():remember(local(base,name),h)
        for row in json.loads((base/'resultados.json').read_text()):
            directory = base/row['evidencias']
            jobs.append((dict(origem='referencia',id=row['desafio']+'_'+str(row['alternativa'])+'_'+row['caso_id'],
                              caso_id=row['caso_id'],desafio=row['desafio'],marcada_correta=row['marcada_correta'],F_original=None),
                         base/'scans/antes'/Path(row['arquivo']).with_suffix('.json'),directory/'scan_depois.json',
                         {row['arquivo']:((directory/'antes.txt').read_bytes(),(directory/'depois.txt').read_bytes())}))
    if args.execucao:
        base = args.execucao.resolve()
        contract = json.loads(remember(base/'contrato_execucao.json').read_text())
        if contract['commit_alvo'] != cat.commit or contract['hashes_catalogo'] != cat.hashes or contract['perfil_sha256'] != profile.hash:
            raise ValueError('Execução/catálogo/perfil divergentes')
        contract_hash=sha(base/'contrato_execucao.json')
        gate = json.loads(remember(base/'sast_antes/reproducao.json').read_text())
        if not gate['reproduzido'] or gate['contrato_execucao_sha256'] != contract_hash:
            raise ValueError('Gate sem proveniência válida')
        before = remember(base/'sast_antes/baseline_raw.json',gate['baseline_sha256'])
        ledger=remember(base/'resultados_consolidados/execucoes.jsonl')
        seen=set()
        for line in ledger.read_text().splitlines():
            row=json.loads(line); tid=row['tentativa_id']
            if not re.fullmatch(r'[A-Za-z0-9_]+',tid) or tid in seen or row['contrato_execucao_sha256'] != contract_hash:
                raise ValueError('Tentativa duplicada/incompatível')
            seen.add(tid)
            for name,h in row['artefatos_sha256'].items():remember(local(base,name),h)
            if row['status_aplicacao'] != 'aplicado':continue
            comparison=local(ROOT,row['artefatos']['comparacao'])
            if (not comparison.is_relative_to(base) or comparison.relative_to(base).as_posix() not in row['artefatos_sha256'] or
                    json.loads(comparison.read_text()).get('falha_operacional')):
                raise ValueError('Comparação sem proveniência ou scan operacionalmente inválido')
            case=cases[row['caso_id']];file=case['arquivo']
            original=remember(local(args.checkout,file),cat.meta['arquivos_fonte'][file]).read_bytes()
            corrected=remember(local(base,'codigos_corrigidos/'+tid+'/'+file)).read_bytes()
            patch_path=remember(local(ROOT,row['artefatos']['patch']))
            if not patch_path.is_relative_to(base) or patch_path.relative_to(base).as_posix() not in row['artefatos_sha256']:
                raise ValueError('Patch sem hash no registro')
            conferir_patch(original,corrected,patch_path.read_bytes())
            after=remember(local(ROOT,row['artefatos']['sast_depois']))
            if not after.is_relative_to(base) or after.relative_to(base).as_posix() not in row['artefatos_sha256']:
                raise ValueError('Scan posterior sem hash no registro')
            jobs.append((dict(origem='execucao',id=tid,caso_id=case['caso_id'],estrategia=row['estrategia_prompt'],
                              F_original=row.get('F_criterio'),F_sem_separacao_original=row.get('F_sem_separacao')),
                         before,after,{file:(original,corrected)}))
    if not jobs:raise ValueError('Nenhuma evidência selecionada')
    output=args.saida.resolve()
    if output.exists() or output.is_symlink():raise ValueError('Destino já existe')
    if output == ROOT or output.is_relative_to(ROOT/'workspace') or any(p.is_relative_to(output) for p in inputs):
        raise ValueError('Saída sobreposta a fontes')
    output.parent.mkdir(parents=True,exist_ok=True)
    lock=output.with_name(output.name+'.lock')
    fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    temporary=None
    try:
        temporary=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent))
        rows=[]
        for row,before,after,sources in jobs:
            a=carregar_scan_perfil(before,args.checkout,profile)
            b=carregar_scan_perfil(after,args.checkout,profile)
            target=chave_caso(cases[row['caso_id']])
            old=v1(a,b,target,sources)
            new=v2(a,b,target,sources,checkout=args.parser_checkout)
            row.update(R_v1=old['R'],M_v1=old['M'],R_v2=new['R'],M_v2=new['M'],
                       ambiguidades_v1=len(old['ambiguos']),ambiguidades_v2=len(new['ambiguos']))
            row['comparacao']='comparacoes/'+row['id']+'.json'
            write(temporary/row['comparacao'],new);rows.append(row)
            print(f"{len(rows)}/{len(jobs)} {row['id']}: {old['R']}/{old['M']} → {new['R']}/{new['M']}",flush=True)
        summary={}
        for origin in sorted({r['origem'] for r in rows}):
            selected=[r for r in rows if r['origem']==origin]
            summary[origin]={'qtd':len(selected),'indeterminadas_v1':sum(r['R_v1'] is None or r['M_v1'] is None for r in selected),
                             'indeterminadas_v2':sum(r['R_v2'] is None or r['M_v2'] is None for r in selected)}
        write(temporary/'resultados.json',rows);write(temporary/'resumo.json',summary)
        write(temporary/'revisoes_associacoes.json',revisions)
        fields=sorted({k for r in rows for k in r})
        with (temporary/'resultados.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        for path,h in inputs.items():
            if sha(path) != h:raise ValueError('Entrada alterada durante reanálise: '+str(path))
        profile.conferir()
        if identidade(args.parser_checkout) != parser_id:raise ValueError('Parser alterado')
        write(temporary/'manifesto.json',{'schema_versao':'1.0','tipo':'recomparacao_offline_calibracao',
              'comparador':VERSAO,'commit_alvo':cat.commit,'perfil_sha256':profile.hash,'parser':parser_id,
              'chamadas_llm':0,'scans_executados':0,'testes_funcionais_executados':False,
              'limites':['M das referências é M_fixture, não global.','F original é apenas transcrito; não foi remensurado.',
                         'Calibração observada; não é validação independente nem estimativa de precisão/recall.'],
              'entradas_sha256':{p.relative_to(ROOT).as_posix():h for p,h in sorted(inputs.items())},
              'artefatos_sha256':{p.relative_to(temporary).as_posix():sha(p) for p in sorted(temporary.rglob('*')) if p.is_file()}})
        if output.exists():raise ValueError('Destino apareceu durante reanálise')
        os.rename(temporary,output);temporary=None
        return summary
    finally:
        if temporary:shutil.rmtree(temporary)
        os.close(fd);lock.unlink()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--referencias',type=Path,default=ROOT/'outputs/auditoria_sast/referencias_codefixes_v1')
    parser.add_argument('--execucao',type=Path)
    parser.add_argument('--checkout',type=Path,default=ROOT/'workspace/catalogo-alvo')
    parser.add_argument('--parser-checkout',type=Path,default=ROOT/'workspace/wt-1')
    parser.add_argument('--catalogo',type=Path,default=ROOT/'outputs/catalogos/ampliado_v1/catalogo_issues.json')
    parser.add_argument('--perfil-sast',type=Path,default=ROOT/'config/perfis/ampliado_piloto_v1/perfil.json')
    parser.add_argument('--revisoes',type=Path,default=ROOT/'config/revisoes_associacoes_v1.yaml')
    parser.add_argument('--saida',required=True,type=Path)
    args=parser.parse_args(argv)
    try:print(json.dumps(executar(args),ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:print(str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
