#!/usr/bin/env python3
"""Avaliação SAST isolada de codefixes; não altera o alvo nem usa LLM/prompts."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402

import argparse
import csv
import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from collections import Counter

import yaml
from pipeline.caminhos import RAIZ_REPO
from pipeline.sast.perfil import carregar as carregar_perfil
from pipeline.sast.semgrep_client import scan_perfil
from pipeline.sast.comparacao import comparar, chave, chave_caso
from scripts.audit.build_challenge_matrix import extrair_evidencias


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def salvar(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def interno(root, nome):
    path = (root / nome).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Arquivo ausente/externo: ' + str(nome))
    return path


def aplicar_trecho(original, referencia, bloco):
    """Envolve o trecho pedagógico no arquivo original, sem adaptar seu conteúdo."""
    lines = original.decode('utf-8').splitlines(keepends=True)
    inicio, fim = bloco['inicio'], bloco['fim']
    if not 1 <= inicio < fim <= len(lines):
        raise ValueError('Intervalo de trecho inválido')
    for n, tipo in ((inicio, 'start'), (fim, 'end')):
        prefix, sep, rest = lines[n-1].partition('vuln-code-snippet ' + tipo)
        if not sep or prefix.strip() not in ('//', '#', '<!--'):
            raise ValueError('Marcador inline/ambíguo; exige revisão manual')
    text = referencia.decode('utf-8')
    if not text.strip():
        raise ValueError('Referência vazia')
    # A normalização é só o separador ao final do trecho. Nenhuma correção de
    # imports, nomes, segurança ou compatibilidade é inferida aqui.
    return (''.join(lines[:inicio]) + text.rstrip('\r\n') + '\n' + ''.join(lines[fim-1:])).encode('utf-8')


def inventariar(checkout, casos):
    keys = sorted({k for c in casos for k in c.get('desafios', [])})
    todos = {c['key'] for c in yaml.safe_load(interno(checkout, 'data/static/challenges.yml').read_text())}
    evidence = extrair_evidencias(checkout, todos)
    base = checkout / 'data/static/codefixes'
    refs, inventario = [], []
    for key in keys:
        alternatives = []
        for p in sorted(base.glob(key + '_*')):
            m = re.fullmatch(re.escape(key) + r'_(\d+)(_correct)?\.(ts|js|html|yml|sol)', p.name)
            if m:
                alternatives.append({'arquivo':p.relative_to(checkout).as_posix(),
                                     'id':int(m[1]), 'correta':bool(m[2])})
        blocos = evidence.get(key, [])
        status = ('sem_codefix_correto' if sum(a['correta'] for a in alternatives) != 1 else
                  'bloco_ausente_ou_multiplo' if len(blocos) != 1 else 'candidato')
        entry = {'desafio':key, 'status':status, 'blocos':blocos,
                 'casos_associados':[c['caso_id'] for c in casos if key in c.get('desafios', [])],
                 'alternativas':alternatives}
        if status == 'candidato':
            bloco = blocos[0]
            original = interno(checkout, bloco['arquivo']).read_bytes()
            try:
                for alternative in alternatives:
                    if Path(alternative['arquivo']).suffix != Path(bloco['arquivo']).suffix:
                        raise ValueError('Extensões diferentes entre trecho e alvo')
                    aplicar_trecho(original, interno(checkout, alternative['arquivo']).read_bytes(), bloco)
            except ValueError as exc:
                entry.update(status='revisao_manual', motivo=str(exc))
            else:
                refs.append(entry)
        inventario.append(entry)
    return refs, inventario


def avaliar(args):
    checkout, saida = args.checkout.resolve(), args.saida.resolve()
    if saida.exists():
        raise ValueError('Saída já existe; escolha um diretório novo')
    if saida.is_relative_to(checkout) or checkout.is_relative_to(saida):
        raise ValueError('Saída sobreposta ao checkout')
    if subprocess.check_output(['git','status','--porcelain'], cwd=checkout):
        raise ValueError('Checkout modificado; não será restaurado')
    casos = json.loads(args.catalogo.read_text())
    commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()
    if {c['commit_alvo'] for c in casos} != {commit}:
        raise ValueError('Commit do checkout diverge do catálogo')
    perfil = carregar_perfil(args.perfil_sast)
    refs, inventario = inventariar(checkout, casos)
    # Nenhuma associação baseada somente no nome do arquivo é promovida a
    # sobreposição com o trecho. Referências sem alvo SAST contido ficam listadas.
    elegiveis = []
    for ref in refs:
        bloco = ref['blocos'][0]
        ref['casos_no_bloco'] = [c['caso_id'] for c in casos if ref['desafio'] in c.get('desafios', [])
            and c['arquivo'] == bloco['arquivo'] and bloco['inicio'] < c['linha_inicio'] <= c['linha_fim'] < bloco['fim']]
        if not perfil.no_escopo(bloco['arquivo']):
            ref['status'] = 'arquivo_fora_escopo'
        elif not ref['casos_no_bloco']:
            ref['status'] = 'sem_alerta_associado_no_bloco'
        else:
            ref['status'] = 'elegivel'
            elegiveis.append(ref)
    fontes = {str(args.catalogo.resolve()):sha(args.catalogo), str(Path(__file__).resolve()):sha(__file__)}
    for path in [checkout/'data/static/challenges.yml', checkout/'.gitignore', perfil.caminho, *perfil.configs]:
        if path.is_file():fontes[str(path)] = sha(path)
    for ref in refs:
        for nome in [ref['blocos'][0]['arquivo'], *[a['arquivo'] for a in ref['alternativas']]]:
            path = interno(checkout,nome);fontes[str(path)] = sha(path)
    saida.parent.mkdir(parents=True,exist_ok=True)
    lock = saida.with_name(saida.name+'.lock')
    fd = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    iniciou = False
    manifesto = {'schema_versao':'1.0', 'tipo':'avaliacao_referencias_pedagogicas_sem_llm',
                 'status':'preparando', 'commit_alvo':commit, 'perfil_sha256':perfil.hash,
                 'comparador':'blocos_unicos_v1', 'fontes_sha256':fontes,
                 'chamadas_llm':0, 'testes_funcionais_executados':False,
                 'escopo':'arquivo completo isolado; M_fixture não é M global da aplicação',
                 'transformacao':'substituição do conteúdo entre marcadores pelo trecho, sem adaptar imports/nomes; newline final normalizado',
                 'limites':['Classificação correct pertence ao desafio, não confirma remoção de cada alerta.',
                            'Trechos pedagógicos podem estar desatualizados ou incompletos; parsing é registrado.',
                            'Sem compilação, testes funcionais ou validação de exploração; F não medido.',
                            'Referências não são enviadas à LLM, prompts, RAG ou catálogo experimental.']}
    rows, baseline_cache = [], {}
    inicio = time.monotonic()
    try:
        saida.mkdir(exist_ok=False);iniciou=True
        salvar(saida/'manifesto.json', manifesto)
        salvar(saida/'inventario.json', inventario)
        with tempfile.TemporaryDirectory(prefix='tcc-referencias-') as tmp:
            root = Path(tmp)
            subprocess.run(['git','init','-q'],cwd=root,check=True)
            ignored = checkout/'.gitignore'
            if ignored.exists():(root/'.gitignore').write_bytes(ignored.read_bytes())
            def scanner(nome, conteudo, destino):
                path = root/nome;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(conteudo)
                try:return scan_perfil(root,perfil,destino,args.semgrep_bin)
                finally:path.unlink()
            total = sum(len(r['alternativas']) for r in elegiveis)
            for ref in elegiveis:
                bloco = ref['blocos'][0];nome = bloco['arquivo']
                original = interno(checkout,nome).read_bytes()
                if nome not in baseline_cache:
                    destino = saida/'scans/antes'/Path(nome).with_suffix('.json')
                    baseline_cache[nome] = scanner(nome,original,destino)
                before = baseline_cache[nome]
                for alternative in ref['alternativas']:
                    referencia = interno(checkout,alternative['arquivo'])
                    corrected = aplicar_trecho(original,referencia.read_bytes(),bloco)
                    ident = ref['desafio'] + '_' + str(alternative['id'])
                    pasta = saida/'variantes'/ident
                    pasta.mkdir(parents=True,exist_ok=False)
                    (pasta/'antes.txt').write_bytes(original);(pasta/'depois.txt').write_bytes(corrected)
                    (pasta/'referencia.txt').write_bytes(referencia.read_bytes())
                    diff = ''.join(difflib.unified_diff(original.decode().splitlines(True),corrected.decode().splitlines(True),fromfile=nome,tofile=nome))
                    (pasta/'alteracao.diff').write_text(diff,encoding='utf-8')
                    after = scanner(nome,corrected,pasta/'scan_depois.json')
                    for case in casos:
                        if case['caso_id'] not in ref['casos_no_bloco']:continue
                        comp = comparar(before,after,chave_caso(case),{nome:(original,corrected)})
                        salvar(pasta/(case['caso_id']+'_comparacao.json'),comp)
                        a = [f for f in before.findings if f.path==nome and f.check_id==case['check_id']]
                        b = [f for f in after.findings if f.path==nome and f.check_id==case['check_id']]
                        reproducao = any(chave(f)==chave_caso(case) for f in a)
                        analisavel = reproducao and not before.falha_operacional and not after.falha_operacional and not before.diagnosticos and not after.diagnosticos
                        row = {'desafio':ref['desafio'],'alternativa':alternative['id'],'marcada_correta':alternative['correta'],
                               'caso_id':case['caso_id'],'arquivo':nome,'regra':case['check_id'],
                               'alertas_regra_antes':len(a),'alertas_regra_depois':len(b),
                               'reproduz_alerta_original':reproducao,'analisavel':analisavel,
                               'alerta_regra_ausente_depois':not b if analisavel else None,
                               'R':comp['R'] if reproducao else None,'M_fixture':comp['M'] if reproducao else None,
                               'ambiguidades':len(comp['ambiguos']), 'F':None,
                               'falha_operacional':before.falha_operacional or after.falha_operacional,
                               'diagnosticos_antes':len(before.diagnosticos),'diagnosticos_depois':len(after.diagnosticos),
                               'evidencias':pasta.relative_to(saida).as_posix()}
                        rows.append(row)
                    salvar(saida/'resultados.json',rows)
                    pronto = len(list((saida/'variantes').iterdir()))
                    salvar(saida/'progresso.json',{'variantes_concluidas':pronto,'total_variantes':total})
                    print(f'{pronto}/{total} {ident} correta={alternative["correta"]} alertas={len(before.findings)}->{len(after.findings)} erros={len(after.diagnosticos)}',flush=True)
        for path,h in fontes.items():
            if sha(path)!=h:raise ValueError('Fonte alterada durante avaliação: '+path)
        perfil.conferir()
        if subprocess.check_output(['git','status','--porcelain'],cwd=checkout):raise ValueError('Checkout mudou durante avaliação')
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()!=commit:raise ValueError('Commit alterado durante avaliação')
        counts = Counter((r['marcada_correta'],r['analisavel'],r['R'],r['M_fixture']) for r in rows)
        resumo = {'casos_catalogo':len(casos),'casos_com_desafios':sum(bool(c['desafios']) for c in casos),
                  'desafios_associados':len(inventario),'desafios_com_referencia_correta':sum(any(a['correta'] for a in r['alternativas']) for r in inventario),
                  'desafios_avaliados':len(elegiveis),'variantes_avaliadas':total,
                  'casos_distintos_avaliados':len({r['caso_id'] for r in rows}),
                  'pares_caso_alternativa':len(rows),'grupos_resultados':[{'correta':k[0],'analisavel':k[1],'R':k[2],'M_fixture':k[3],'quantidade':n} for k,n in sorted(counts.items(),key=lambda x:str(x[0]))]}
        salvar(saida/'resumo.json',resumo)
        if rows:
            with (saida/'resultados.csv').open('w',encoding='utf-8',newline='') as stream:
                w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        manifesto.update(status='concluido',duracao_s=time.monotonic()-inicio,resumo=resumo)
    except BaseException as exc:
        manifesto.update(status='parcial',erro=type(exc).__name__+': '+str(exc))
        raise
    finally:
        if iniciou:
            manifesto['artefatos_sha256'] = {p.relative_to(saida).as_posix():sha(p) for p in sorted(saida.rglob('*')) if p.is_file() and p.name!='manifesto.json'}
            salvar(saida/'manifesto.json',manifesto)
        os.close(fd);lock.unlink()
    return resumo


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout',type=Path,default=RAIZ_REPO/'workspace/catalogo-alvo')
    parser.add_argument('--catalogo',type=Path,default=RAIZ_REPO/'outputs/catalogos/ampliado_v1/catalogo_issues.json')
    parser.add_argument('--perfil-sast',type=Path,default=RAIZ_REPO/'config/perfis/ampliado_piloto_v1/perfil.json')
    parser.add_argument('--semgrep-bin',default=str(RAIZ_REPO/'.venv/bin/semgrep'))
    parser.add_argument('--saida',type=Path,required=True)
    args=parser.parse_args(argv)
    try:print(json.dumps(avaliar(args),ensure_ascii=False,indent=2))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('ERRO: '+str(exc),file=sys.stderr);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
