"""Compara antes × depois da reorganização do código (fase 2), aplicando o mapa de nomes antigos → novos.

Mudanças esperadas (e só elas): caminhos e nomes de módulos/scripts, hashes do código que mudou nos imports,
baseline e referência Docker novos (mesma imagem local), e o que deriva disso. Todo o resto precisa ser igual.
Uso: python3 comparar_fase2.py <pasta_fase2>
"""
import filecmp
import json
import os
import re
import sys
from pathlib import Path

base = Path(sys.argv[1]).resolve()
A, D = base / 'antes', base / 'depois'
mapa = json.load(open(base / 'mapa_codigo.json'))
ARQ, MOD = mapa['arquivos'], mapa['modulos']
NOME = {Path(a).name: Path(n).name for a, n in ARQ.items() if a.startswith('src/')}
falhas, notas = [], []


def item(nome, ok, detalhe=''):
    print(f"{'OK   ' if ok else 'FALHA'} {nome}" + (f' — {detalhe}' if detalhe else ''))
    if not ok:
        falhas.append(nome)


def nota(t):
    print(f'NOTA  {t}')
    notas.append(t)


def ler(p):
    return Path(p).read_text(encoding='utf-8', errors='replace')


def jl(p):
    return json.loads(ler(p))


re_arq = re.compile(r'(?<![A-Za-z0-9_.-])(' + '|'.join(re.escape(k) for k in sorted(ARQ, key=len, reverse=True)) + r')(?![A-Za-z0-9_-])')
re_mod = re.compile(r'(?<![A-Za-z0-9_.])(' + '|'.join(re.escape(k) for k in sorted(MOD, key=len, reverse=True)) + r')(?![A-Za-z0-9_])')


def traduzir(t):
    """Aplica ao texto 'antes' a mesma troca de nomes feita no código."""
    t = re_arq.sub(lambda m: ARQ[m.group(1)], t)
    return re_mod.sub(lambda m: MOD[m.group(1)], t)


# 01 identidade científica
ia, id_ = jl(A / '01_identidade.json'), jl(D / '01_identidade.json')
for chave in ('componentes_prompt', 'roteiro_sha256', 'base_rag_sha256', 'perfis', 'catalogo'):
    item(f'01 {chave} idêntico', ia[chave] == id_[chave])
comp_a = {ARQ.get(k, k): v for k, v in ia['componentes'].items()}
item('01 componentes do contrato: os mesmos 30 arquivos (mapeados)', sorted(comp_a) == sorted(id_['componentes']),
     f"{len(comp_a)} × {len(id_['componentes'])}")
iguais = sum(comp_a[k] == id_['componentes'].get(k) for k in comp_a)
nota(f'componentes com conteúdo idêntico: {iguais} de {len(comp_a)} (os demais mudaram só nos imports)')
ca, cd = dict(ia['cobertura_identidade']), dict(id_['cobertura_identidade'])
adapt_a = {NOME.get(k, k): v for k, v in ca.pop('adaptadores_sha256').items()}
adapt_d = cd.pop('adaptadores_sha256')
item('01 identidade de cobertura idêntica fora dos adaptadores (revisão, mapa, conjunto D, testes adicionais, execução)', ca == cd)
item('01 adaptadores de cobertura: os mesmos 5 arquivos (renomeados)', sorted(adapt_a) == sorted(adapt_d), ', '.join(sorted(adapt_d)))
ra = {ARQ.get(k, k): v for k, v in ia['referencia_docker_entradas'].items()}
rd = id_['referencia_docker_entradas']
item('01 referência Docker: as mesmas 17 entradas (mapeadas)', sorted(ra) == sorted(rd))
nao_codigo = [k for k in rd if not k.startswith('src/')]
item(f'01 referência Docker: as {len(nao_codigo)} entradas que não são código têm o mesmo hash (Dockerfile, locks, configs, testes)',
     all(ra[k] == rd[k] for k in nao_codigo))
nota(f"baseline oficial: antes {ia['baseline_oficial_sha256'][:12]}… (oficial_v1), depois {id_['baseline_oficial_sha256'][:12]}… (oficial_v2)")


# 02 arquivos
def inventario(p):
    out = {}
    for linha in ler(p).splitlines():
        h, _, c = linha.partition('  ')
        out[c] = h
    return out


fa, fd = inventario(A / '02_arquivos.txt'), inventario(D / '02_arquivos.txt')
fa_m = {ARQ.get(k, k): v for k, v in fa.items()}
sumiram = sorted(set(fa_m) - set(fd))
surgiram = sorted(set(fd) - set(fa_m))
mudaram = sorted(k for k in set(fa_m) & set(fd) if fa_m[k] != fd[k])
dados = re.compile(r'^(config/(?!execucao_docker_)|knowledge_base/|rules/|tests/functional/|Dockerfile$|compose\.yaml$|requirements|docker/juice-shop/)')
dados_mudaram = [k for k in mudaram + sumiram if dados.search(k) and not k.endswith('README.md')]
item('02 nenhum dado de entrada mudou (configs congeladas, base RAG, regras, testes próprios, Dockerfile, locks)',
     not dados_mudaram, ', '.join(dados_mudaram))
print(f'      arquivos: {len(fa)} antes, {len(fd)} depois; {len(mudaram)} com conteúdo alterado; '
      f'{len(surgiram)} novos; {len(sumiram)} sem correspondente')
for k in surgiram:
    print(f'        novo: {k}')
for k in sumiram:
    print(f'        sem correspondente: {k}')
oa, od = inventario(A / '02_outputs.txt'), inventario(D / '02_outputs.txt')
item('02b outputs/: nada removido nem alterado', all(od.get(k) == v for k, v in oa.items()),
     f'{len(set(od) - set(oa))} arquivos novos: ' + ', '.join(sorted({"/".join(k.split("/")[:4]) for k in set(od) - set(oa)})))


# 03 testes
def testes(p):
    linhas = ler(p).splitlines()
    res = {}
    for i, l in enumerate(linhas):
        m = re.match(r'^(test\S+) \((\S+)\)', l)
        if m:
            for j in range(i, min(i + 40, len(linhas))):
                s = re.search(r'\.\.\. (ok|FAIL|ERROR|skipped.*)$', linhas[j])
                if s:
                    res[f'{m.group(2)}.{m.group(1)}'] = s.group(1)
                    break
    return res, ler(p).strip().splitlines()[-1]


(ta, ea), (td, ed) = testes(A / '03_testes.txt'), testes(D / '03_testes.txt')
item('03 testes Python: mesmos testes, mesmos resultados', ta == td and ea == ed, f'{len(ta)} × {len(td)} ({ea} / {ed})')
item('04 testes das regras Semgrep', ler(A / '04_regras.txt').splitlines()[-3:] == ler(D / '04_regras.txt').splitlines()[-3:])

# 05 e 10: execuções
VOLATEIS = re.compile(r'^(duracao|tempos?_|espera|inicio|fim)|_s$|^worktree$|timestamp', re.I)
DERIVADOS = {'artefatos_sha256', 'fontes_sha256', 'evidencia_sha256', 'baseline_sha256', 'time', 'contrato_execucao_sha256'}


def norm_str(t):
    t = re.sub(r'/tmp/tcc_cobertura_[A-Za-z0-9_]+', '/tmp/<tmp>', t)
    t = re.sub(r'\(\d+(\.\d+)?ms\)', '(<ms>)', t)
    t = re.sub(r'(time|duration_ms)(=| )"?[0-9.]+"?', r'\1=<t>', t)
    t = re.sub(r'wt-\d+', 'wt-N', t)
    t = re.sub(r'hostname="[0-9a-f]+"', 'hostname=<container>', t)
    return traduzir(t)


def limpar(o):
    if isinstance(o, dict):
        return {k: limpar(v) for k, v in o.items() if not VOLATEIS.search(k) and k not in DERIVADOS}
    if isinstance(o, list):
        return [limpar(v) for v in o]
    if isinstance(o, str):
        return norm_str(o)
    return o


def diff_dir(x, y):
    dif = []

    def rec(c):
        dif.extend(str(Path(c.left).relative_to(x) / f) for f in c.diff_files + c.left_only + c.right_only)
        for s in c.subdirs.values():
            rec(s)
    rec(filecmp.dircmp(x, y))
    return dif


IDENT = ('validacao', 'prompts_validacao_sha256', 'inferencia', 'baseline_testes_sha256')
for nome in ('05_preflight', '10_dryrun'):
    c_a, c_d = jl(A / nome / 'contrato_execucao.json'), jl(D / nome / 'contrato_execucao.json')
    outros = sorted(k for k in set(c_a) | set(c_d) if k not in IDENT and c_a.get(k) != c_d.get(k))
    item(f'{nome}: contrato igual fora dos campos de identidade do código e do baseline', not outros, ', '.join(outros))
    nota(f"{nome}: campos de identidade que mudaram como esperado: "
         f"{', '.join(k for k in IDENT if c_a.get(k) != c_d.get(k)) or 'nenhum'}")
    for sub in ('prompts', 'respostas_llm', 'patches', 'codigos_corrigidos', 'comparacoes'):
        if (A / nome / sub).exists():
            dif = diff_dir(A / nome / sub, D / nome / sub)
            item(f'{nome}/{sub}: idênticos byte a byte', not dif, ', '.join(dif[:5]))
    for sub in ('testes', 'sast_depois', 'sast_antes'):
        if not (A / nome / sub).exists():
            continue
        dif = []
        for pa in sorted((A / nome / sub).rglob('*.json')):
            pd = D / nome / sub / pa.relative_to(A / nome / sub)
            if not pd.exists() or limpar(jl(pa)) != limpar(jl(pd)):
                dif.append(pa.name)
        item(f'{nome}/{sub}: iguais após normalização ({len(list((A / nome / sub).rglob("*.json")))} arquivos)', not dif, ', '.join(dif[:5]))
    item(f'{nome} terminou com sucesso nas duas', ler(A / f'{nome}.log').strip().endswith('exit=0') and ler(D / f'{nome}.log').strip().endswith('exit=0'))

CAMPOS = ('caso_id', 'estrategia_prompt', 'R', 'F', 'M', 'F_criterio', 'F_marcador', 'F_sem_separacao',
          'classificacao_final', 'status_aplicacao', 'hash_prompt', 'tier_falha')


def chave(p):
    return sorted(tuple(str(json.loads(l).get(c)) for c in CAMPOS) for l in ler(p).splitlines() if l.strip())


ra_, rd_ = chave(A / '10_dryrun/resultados_consolidados/execucoes.jsonl'), chave(D / '10_dryrun/resultados_consolidados/execucoes.jsonl')
item(f'10 dry-run: as {len(ra_)} tentativas têm os mesmos R, F, M, classificação, aplicação e hash do prompt', ra_ == rd_)
for nome in ('05_preflight_METRICAS', '10_dryrun_METRICAS'):
    for csvn in ('metricas_gerais.csv', 'metricas_por_estrategia.csv', 'metricas_por_caso.csv', 'casos.csv'):
        item(f'{nome}/{csvn} idêntico', ler(A / nome / csvn) == ler(D / nome / csvn))

# 06 métricas oficiais
item('06 reconsolidação da campanha oficial idêntica ao arquivado (antes e depois)',
     ler(A / '06_diff_com_arquivado.txt').strip() == 'diff_exit=0' and ler(D / '06_diff_com_arquivado.txt').strip() == 'diff_exit=0')

# 07 executar e 08 make: só os nomes trocados e o ID da imagem oficial
ex_a, ex_d = traduzir(ler(A / '07_executar.txt')), ler(D / '07_executar.txt')
base_a = jl(A / '05_preflight/contrato_execucao.json').get('baseline_testes_sha256')
item('07 comandos do executar.py iguais, a menos dos nomes novos e do baseline do config Docker',
     re.sub(r'outputs/[^ ]*baseline_testes\.json', '<baseline>', ex_a) == re.sub(r'outputs/[^ ]*baseline_testes\.json', '<baseline>', ex_d))
mk = lambda t: re.sub(r'sha256:[0-9a-f]{64}', '<imagem>', t)
item('08 Makefile (make -n) igual, a menos do ID da imagem oficial', mk(traduzir(ler(A / '08_make.txt'))) == mk(ler(D / '08_make.txt')))

# 09 painel
dif = []
for pa in sorted((A / '09_painel').iterdir()):
    pd = D / '09_painel' / pa.name
    ta_, td_ = ler(pa), ler(pd)
    if pa.name.endswith('.body') and ta_.lstrip().startswith(('{', '[')):
        if limpar(json.loads(ta_)) != limpar(json.loads(td_)):
            dif.append(pa.name)
    elif norm_str(ta_) != norm_str(td_) and not pa.name.endswith('.headers'):
        dif.append(pa.name)
item('09 painel: páginas e API iguais', not dif, ', '.join(dif))

# 11 links
t = ler(D / '11_links.txt')
q = int(re.search(r'quebrados: (\d+)', t).group(1))
item('11 nenhum link interno quebrado na documentação', q == 0, t.splitlines()[0])

# 12 referência
nota('12 conferência da referência Docker: antes = ' + ler(A / '12_referencia.txt').strip().splitlines()[-2][:90]
     + ' | depois = ' + ' '.join(ler(D / '12_referencia.txt').split())[:120])
item('12 referência Docker nova conferida nesta máquina', ler(D / '12_referencia.txt').strip().endswith('exit=0'))

# 13 imports
ma, md = jl(A / '13_imports.json'), jl(D / '13_imports.json')
item('13 todos os módulos e scripts importam (mesmos arquivos, mapeados)',
     sorted(ARQ.get(k, k) for k in ma) == sorted(md) and all(v == 'ok' for v in md.values()), f'{len(ma)} × {len(md)}')

print()
print('RESULTADO:', 'tudo igual no que é funcional (diferenças só as esperadas)' if not falhas else
      f'{len(falhas)} diferença(s): ' + '; '.join(falhas))
sys.exit(1 if falhas else 0)
