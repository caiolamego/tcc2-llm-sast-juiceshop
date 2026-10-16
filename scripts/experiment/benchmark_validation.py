#!/usr/bin/env python3
"""Replay de patches arquivados: SAST/testes reais, sem cliente ou geração LLM."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import os
import resource
import signal
import subprocess
import threading
import time
from uuid import uuid4

from pipeline.caminhos import RAIZ_REPO
from pipeline.metrics.loader import carregar
from pipeline.sast.semgrep_client import scan_perfil
from pipeline.sast.comparacao import gate
from pipeline.target.workspace import PoolWorktrees
from pipeline.validation.engine import medir
from pipeline.validation.identity import digest, hash_json
from pipeline.validation.policy import argumentos, identidade


class Recursos:
    """RSS somado dos descendentes; memória compartilhada pode ser contada duas vezes."""
    def __init__(self):
        self.parar = threading.Event()
        self.pico_rss_kib = 0
        self.min_mem_disponivel_kib = None
        self.thread = threading.Thread(target=self._amostrar,daemon=True)

    def _amostrar(self):
        while not self.parar.is_set():
            try:
                raw = subprocess.check_output(['ps','-e','-o','pid=,ppid=,rss='],text=True,timeout=5)
                processos = [tuple(map(int,l.split())) for l in raw.splitlines()]
                filhos = {os.getpid()}
                while True:
                    novos = {pid for pid,ppid,_ in processos if ppid in filhos} - filhos
                    if not novos:break
                    filhos.update(novos)
                self.pico_rss_kib = max(self.pico_rss_kib,sum(rss for pid,_,rss in processos if pid in filhos))
                for l in Path('/proc/meminfo').read_text().splitlines():
                    if l.startswith('MemAvailable:'):
                        value=int(l.split()[1]);self.min_mem_disponivel_kib=min(self.min_mem_disponivel_kib or value,value)
            except (OSError,ValueError,subprocess.SubprocessError):pass
            self.parar.wait(.5)


def salvar(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    os.replace(tmp,path)


def replay(args):
    origem, saida = args.origem.resolve(), args.saida.resolve()
    if not saida.is_relative_to(RAIZ_REPO/'outputs/feature05') or saida == RAIZ_REPO/'outputs/feature05':
        raise ValueError('Benchmark requer saída nova sob outputs/feature05/')
    if saida.is_relative_to(origem) or origem.is_relative_to(saida):
        raise ValueError('Saída sobreposta à origem')
    if saida.exists():
        raise ValueError('Destino já existe; escolha uma saída nova')
    contrato = json.loads((origem/'contrato_execucao.json').read_text())
    entrada = carregar(origem,contrato['execucao'],args.catalogo)
    if digest(args.baseline_testes) != contrato['baseline_testes_sha256']:
        raise ValueError('Baseline funcional diverge da origem')
    perfil = entrada.perfil
    casos = {c['caso_id']:c for c in entrada.catalogo.casos}
    jobs = {}
    for linha in entrada.linhas:
        referencia = linha['artefatos'].get('patch')
        if not referencia: continue
        patch = Path(referencia)
        patch = patch if patch.is_absolute() else RAIZ_REPO/patch
        # O loader já conferiu o ledger; confere também o patch efetivamente usado.
        rel = patch.resolve().relative_to(origem).as_posix()
        if digest(patch) != linha['artefatos_sha256'][rel]:
            raise ValueError('Patch de origem adulterado')
        grupo = jobs.setdefault(linha['caso_id'],[])
        if not args.somente_primeiro or not grupo:
            grupo.append((linha,patch))
    if not jobs: raise ValueError('Nenhum patch verificável na origem')
    for i in range(1,args.k+1):
        wt = RAIZ_REPO/f'workspace/wt-{i}'
        if not wt.is_dir() or not PoolWorktrees.esta_limpo(wt):
            raise ValueError(f'Worktree ausente ou modificada: {wt.name}')
        for necessario in ('build/server.js', 'frontend/dist/frontend/index.html'):
            if not (wt/necessario).is_file():
                raise ValueError(f'Preparação incompleta em {wt.name}: falta {necessario}; '
                                 'prepare o build antes do benchmark')
    pool = PoolWorktrees(RAIZ_REPO/'workspace',args.k,entrada.catalogo.commit)
    lock_path = saida.with_name(saida.name+'.lock')
    saida.parent.mkdir(parents=True,exist_ok=True)
    fd = os.open(lock_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    parar, gravacao, api_lock = threading.Event(), threading.Lock(), threading.Lock()
    old_handler = signal.signal(signal.SIGINT,lambda *_:parar.set())
    rows, erros = [], []
    recursos = Recursos()
    inicio = time.monotonic()
    criou_saida = False
    manifesto = {'schema_versao':'1.0','tipo':'benchmark_replay_sem_llm','status':'preparando',
                 'chamadas_llm':0,'origem_execucao':contrato['execucao'],
                 'commit_alvo':entrada.catalogo.commit,'fontes_sha256':entrada.fontes,
                 'k':args.k,'repeticoes':args.repeticoes,'cache':args.cache_validacao}
    manifesto['benchmark_sha256'] = digest(__file__)
    try:
        saida.mkdir(exist_ok=False)
        criou_saida = True
        salvar(saida/'manifesto.json',manifesto)
        recursos.thread.start()
        manifesto['validacao'] = identidade(args,[RAIZ_REPO/f'workspace/wt-{i}' for i in range(1,args.k+1)])
        with pool.alugar() as wt:
            baseline = scan_perfil(wt,perfil,saida/'preparacao/baseline_raw.json',args.semgrep_bin)
        reproducao = gate(entrada.catalogo,baseline)
        salvar(saida/'preparacao/reproducao.json',reproducao)
        if not reproducao['reproduzido']: raise ValueError('Perfil não reproduz os 78 casos')
        manifesto['preparacao_s'] = time.monotonic()-inicio
        manifesto['status']='executando'
        salvar(saida/'manifesto.json',manifesto)
        cronometro = time.monotonic()
        def processar(item):
            caso, patches = item
            espera_inicio = time.monotonic()
            with pool.alugar() as wt:
                espera_wt = time.monotonic()-espera_inicio
                for repeticao in range(1,args.repeticoes+1):
                    for linha, patch in patches:
                        if parar.is_set() or (args.arquivo_parada and args.arquivo_parada.exists()): return
                        t = time.monotonic()
                        tid = f"{linha['tentativa_id']}_REP{repeticao}"
                        pasta = saida/'tentativas'/tid
                        pasta.mkdir(parents=True,exist_ok=False)
                        PoolWorktrees.restaurar(wt)
                        texto = subprocess.check_output(['git','apply','--numstat',str(patch)],cwd=wt,text=True)
                        arquivos = [l.split('\t',2)[2] for l in texto.splitlines()]
                        antes = {}
                        for nome in arquivos:
                            path = (wt/nome).resolve()
                            if not path.is_relative_to(wt.resolve()) or not path.is_file() or not perfil.no_escopo(nome):
                                raise ValueError('Patch fora do escopo ou cria/remove arquivo')
                            antes[nome] = path.read_bytes()
                        try:
                            subprocess.run(['git','apply',str(patch)],cwd=wt,check=True,timeout=60)
                            fontes = {nome:(raw,(wt/nome).read_bytes()) for nome,raw in antes.items()}
                            preparo = time.monotonic()-t
                            _, comp, validacao, medicao = medir(wt,casos[caso],fontes,baseline,perfil,
                                args.baseline_testes,pasta/'sast_raw.json',args,api_lock,
                                origem={'benchmark':saida.name,'replay_id':tid},cache_dir=args.cache_dir,
                                parar=parar.is_set)
                            salvar(pasta/'comparacao.json',comp)
                            salvar(pasta/'validacao.json',validacao.to_dict())
                        finally:
                            restauracao = time.monotonic()
                            PoolWorktrees.restaurar(wt)
                            restauracao = time.monotonic()-restauracao
                        row = {'replay_id':tid,'caso_id':caso,'estrategia':linha['estrategia_prompt'],
                               'repeticao':repeticao,'patch_sha256':digest(patch),'worktree':wt.name,
                               'R':comp['R'],'M':comp['M'], **{f'F_{d}':int(getattr(validacao,f'F_{d}')) for d in ('sem_separacao','marcador','criterio')},
                               'falhas_persistentes':validacao.testes_falhos_novos,
                               'falhas_intermitentes':validacao.testes_falhos_intermitentes,
                               'selecao':validacao.selecao, 'etapas':medicao['etapas_validacao'],
                               'preparacao_s':preparo,'restauracao_s':restauracao,'espera_worktree_s':espera_wt,
                               'total_s':time.monotonic()-t, **medicao}
                        with gravacao:
                            rows.append(row)
                            with (saida/'replays.jsonl').open('a',encoding='utf-8') as stream:
                                stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
                        print(f"{caso} {linha['estrategia_prompt']} rep={repeticao} {row['total_s']:.1f}s R/F/M={comp['R']}/{int(validacao.F_criterio)}/{comp['M']} cache="+
                              str({k:v['hit'] for k,v in medicao['cache_validacao'].items()}),flush=True)
        with ThreadPoolExecutor(max_workers=args.k) as executor:
            futures = [executor.submit(processar,item) for item in sorted(jobs.items())]
            for future in futures:
                try: future.result()
                except Exception as exc:
                    erros.append(f'{type(exc).__name__}: {exc}');parar.set()
        entrada.revalidar()
        if digest(__file__) != manifesto['benchmark_sha256']:
            raise ValueError('Implementação do benchmark alterada durante execução')
        manifesto.update(status='parcial' if parar.is_set() else 'concluido',erros=erros,
                         tempo_parede_execucao_s=time.monotonic()-cronometro,
                         tempo_total_s=time.monotonic()-inicio,
                         maxrss_filhos_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                         limite_memoria='maxrss é máximo de um filho, não soma dos workers',
                         pico_rss_descendentes_kib=recursos.pico_rss_kib,
                         min_memoria_disponivel_kib=recursos.min_mem_disponivel_kib,
                         limite_rss_somado='Amostras a cada 0,5 s; páginas compartilhadas podem ser contadas mais de uma vez',
                         observacoes=len(rows),limpas=all(PoolWorktrees.esta_limpo(RAIZ_REPO/f'workspace/wt-{i}') for i in range(1,args.k+1)))
        salvar(saida/'resultados.json',sorted(rows,key=lambda r:r['replay_id']))
        columns=['replay_id','caso_id','estrategia','repeticao','R','F_criterio','F_sem_separacao','F_marcador','M','total_s','preparacao_s','restauracao_s','espera_worktree_s']
        with (saida/'tempos.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,columns,extrasaction='ignore');writer.writeheader();writer.writerows(sorted(rows,key=lambda r:r['replay_id']))
        salvar(saida/'manifesto.json',manifesto)
        (saida/'RESUMO.md').write_text(f"# Replay sem LLM\n\nStatus: {manifesto['status']}. {len(rows)} observações; K={args.k}.\n\nTempo de execução: {manifesto['tempo_parede_execucao_s']:.3f} s. Preparação: {manifesto['preparacao_s']:.3f} s.\n\nNão integra métricas de geração LLM. Consulte resultados.json e tempos.csv.\n",encoding='utf-8')
        return 1 if erros or parar.is_set() else 0
    except BaseException as exc:
        if criou_saida:
            manifesto.update(status='falhou',erro=f'{type(exc).__name__}: {exc}')
            salvar(saida/'manifesto.json',manifesto)
        raise
    finally:
        recursos.parar.set()
        if recursos.thread.is_alive():recursos.thread.join(timeout=6)
        signal.signal(signal.SIGINT,old_handler)
        os.close(fd);lock_path.unlink()


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--origem',type=Path,required=True)
    ap.add_argument('--saida',type=Path,required=True)
    ap.add_argument('--catalogo',type=Path,default=RAIZ_REPO/'outputs/catalogos/ampliado_v1/catalogo_issues.json')
    ap.add_argument('--baseline-testes',type=Path,default=RAIZ_REPO/'outputs/feature02/validacao/baseline_testes.json')
    ap.add_argument('--semgrep-bin',default=str(RAIZ_REPO/'.venv/bin/semgrep'))
    ap.add_argument('--k',type=int,choices=(1,2),default=1)
    ap.add_argument('--repeticoes',type=int,default=1)
    ap.add_argument('--somente-primeiro',action='store_true')
    ap.add_argument('--arquivo-parada',type=Path)
    ap.add_argument('--cache-dir',type=Path,default=RAIZ_REPO/'.cache/validacao/v1')
    argumentos(ap)
    args=ap.parse_args(argv)
    if args.repeticoes < 1: ap.error('--repeticoes deve ser positivo')
    try: return replay(args)
    except (ValueError,OSError,KeyError,RuntimeError,subprocess.SubprocessError) as exc:
        print(f'ERRO: {exc}',file=sys.stderr);return 1


if __name__=='__main__': raise SystemExit(main())
