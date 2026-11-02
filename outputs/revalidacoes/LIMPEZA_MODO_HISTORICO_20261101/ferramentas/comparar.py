"""Compara antes × depois da retirada do modo histórico (E01–E03) do código.

Mudanças esperadas (e só elas): arquivos removidos, conteúdo dos arquivos editados, a identidade do código no
contrato (campo 'validacao') e o que deriva dela. Referência Docker, baseline, prompts, catálogo, perfis, testes,
comandos e resultados precisam ficar iguais.
Uso: python3 comparar.py <pasta com antes/ e depois/>
"""
import filecmp
import json
import re
import sys
from pathlib import Path

base = Path(sys.argv[1]).resolve()
A, D = base / 'antes', base / 'depois'
REMOVIDOS = {
    'src/pipeline/legado/filtro.py',
    'scripts/experimento/gerar_catalogo_historico.py',
    'scripts/experimento/marcar_desafios_historicos.py',
    'scripts/experimento/validar_cenarios_camadas.py',
    'scripts/experimento/medir_custo_validacao.py',
    'scripts/relatorios/relatorio_baseline_historico.py',
}
falhas = []


def item(nome, ok, detalhe=''):
    print(f"{'OK   ' if ok else 'FALHA'} {nome}" + (f' — {detalhe}' if detalhe else ''))
    if not ok:
        falhas.append(nome)


def nota(t):
    print(f'NOTA  {t}')


def ler(p):
    return Path(p).read_text(encoding='utf-8', errors='replace')


def jl(p):
    return json.loads(ler(p))


# 01 identidade científica
ia, id_ = jl(A / '01_identidade.json'), jl(D / '01_identidade.json')
for chave in ('componentes_prompt', 'roteiro_sha256', 'base_rag_sha256', 'perfis', 'catalogo', 'cobertura_identidade',
              'referencia_docker_entradas', 'referencia_docker_json_sha256', 'baseline_oficial_sha256'):
    item(f'01 {chave} idêntico', ia[chave] == id_[chave])
ca, cd = ia['componentes'], id_['componentes']
item('01 componentes do contrato: os de antes menos os removidos', sorted(set(ca) - REMOVIDOS) == sorted(cd),
     f'{len(ca)} × {len(cd)}')
mudaram = sorted(k for k in cd if ca.get(k) != cd[k])
nota(f'componentes com conteúdo alterado: {", ".join(mudaram) or "nenhum"}')


# 02 arquivos
def inventario(p):
    out = {}
    for linha in ler(p).splitlines():
        h, _, c = linha.partition('  ')
        out[c] = h
    return out


fa, fd = inventario(A / '02_arquivos.txt'), inventario(D / '02_arquivos.txt')
sumiram, surgiram = sorted(set(fa) - set(fd)), sorted(set(fd) - set(fa))
alterados = sorted(k for k in set(fa) & set(fd) if fa[k] != fd[k])
item('02 sumiram exatamente os arquivos previstos', set(sumiram) == REMOVIDOS, ', '.join(sumiram))
item('02 nenhum arquivo novo', not surgiram, ', '.join(surgiram))
dados = re.compile(r'^(config/|knowledge_base/|rules/|tests/functional/|tests/integration/|Dockerfile$|compose\.yaml$|requirements|docker/)')
dados_mudaram = [k for k in alterados if dados.search(k) and not k.endswith('README.md')]
item('02 nenhum dado de entrada mudou (configs, base RAG, regras, testes próprios, Docker)',
     not dados_mudaram, ', '.join(dados_mudaram))
print('      alterados: ' + ', '.join(alterados))
oa, od = inventario(A / '02_outputs.txt'), inventario(D / '02_outputs.txt')
outputs_mudaram = sorted(k for k, v in oa.items() if od.get(k) != v)
item('02b outputs/: nada removido nem alterado além do índice (outputs/README.md)',
     outputs_mudaram in ([], ['outputs/README.md']), f'{len(set(od) - set(oa))} arquivos novos; alterados: {outputs_mudaram}')


# 03 e 04 testes
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
item('03 nenhum teste falhou', all(v == 'ok' or v.startswith('skipped') for v in td.values()))
item('04 testes das regras Semgrep', ler(A / '04_regras.txt').splitlines()[-3:] == ler(D / '04_regras.txt').splitlines()[-3:])

# 05 e 10: execuções
VOLATEIS = re.compile(r'^(duracao|tempos?_|espera|inicio|fim)|_s$|^worktree$|timestamp', re.I)
# 'chave' (cache_validacao.sast/funcional) é o hash de uma identidade que inclui a lista de arquivos do código
# (medicao.py: 'implementacao': componentes()); muda pelo mesmo motivo que contrato_execucao_sha256.
DERIVADOS = {'artefatos_sha256', 'fontes_sha256', 'evidencia_sha256', 'baseline_sha256', 'time', 'contrato_execucao_sha256', 'chave'}


def norm_str(t):
    t = re.sub(r'/tmp/tcc_cobertura_[A-Za-z0-9_]+', '/tmp/<tmp>', t)
    t = re.sub(r'\(\d+(\.\d+)?ms\)', '(<ms>)', t)
    t = re.sub(r'(time|duration_ms)(=| )"?[0-9.]+"?', r'\1=<t>', t)
    t = re.sub(r'wt-\d+', 'wt-N', t)
    return re.sub(r'hostname="[0-9a-f]+"', 'hostname=<container>', t)


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


for nome in ('05_preflight', '10_dryrun'):
    c_a, c_d = jl(A / nome / 'contrato_execucao.json'), jl(D / nome / 'contrato_execucao.json')
    outros = sorted(k for k in set(c_a) | set(c_d) if k != 'validacao' and c_a.get(k) != c_d.get(k))
    item(f'{nome}: contrato igual fora da identidade do código', not outros, ', '.join(outros))
    va, vd = dict(c_a.get('validacao', {})), dict(c_d.get('validacao', {}))
    ima, imd = va.pop('implementacao', {}), vd.pop('implementacao', {})
    item(f'{nome}: validação igual fora da lista de arquivos do código', va == vd)
    item(f'{nome}: lista de arquivos do código = antes menos os removidos', sorted(set(ima) - REMOVIDOS) == sorted(imd))
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
ra_ = [json.loads(l) for l in ler(A / '10_dryrun/resultados_consolidados/execucoes.jsonl').splitlines() if l.strip()]
rd_ = [json.loads(l) for l in ler(D / '10_dryrun/resultados_consolidados/execucoes.jsonl').splitlines() if l.strip()]
chave = lambda ls: sorted(tuple(str(l.get(c)) for c in CAMPOS) for l in ls)
item(f'10 dry-run: as {len(ra_)} tentativas têm os mesmos R, F, M, classificação, aplicação e hash do prompt', chave(ra_) == chave(rd_))
por_id = lambda ls: {l['tentativa_id']: limpar(l) for l in ls}
pa_, pd_ = por_id(ra_), por_id(rd_)
item('10 dry-run: registros completos iguais após normalização (mesmos campos, mesma ordem)',
     pa_ == pd_ and all(list(pa_[k]) == list(pd_[k]) for k in pa_),
     ', '.join(k for k in pa_ if pa_[k] != pd_.get(k))[:200])
sa = limpar(jl(A / '10_dryrun/resultados_consolidados/LIMPEZA_DRY_sessoes.json'))
sd = limpar(jl(D / '10_dryrun/resultados_consolidados/LIMPEZA_DRY_sessoes.json'))
item('10 dry-run: registro da sessão igual após normalização (mesmos campos, mesma ordem)',
     sa == sd and [list(s) for s in sa] == [list(s) for s in sd])
for nome in ('05_preflight_METRICAS', '10_dryrun_METRICAS'):
    for csvn in ('metricas_gerais.csv', 'metricas_por_estrategia.csv', 'metricas_por_caso.csv', 'casos.csv'):
        item(f'{nome}/{csvn} idêntico', ler(A / nome / csvn) == ler(D / nome / csvn))

# 06 métricas oficiais
item('06 reconsolidação da campanha oficial idêntica ao arquivado (antes e depois)',
     ler(A / '06_diff_com_arquivado.txt').strip() == 'diff_exit=0' and ler(D / '06_diff_com_arquivado.txt').strip() == 'diff_exit=0')

# 07 executar e 08 make
item('07 comandos do executar.py idênticos', ler(A / '07_executar.txt') == ler(D / '07_executar.txt'))
item('08 Makefile (make -n) idêntico', ler(A / '08_make.txt') == ler(D / '08_make.txt'))

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
item('12 referência Docker conferida (antes e depois)',
     ler(A / '12_referencia.txt').strip().endswith('exit=0') and ler(D / '12_referencia.txt').strip().endswith('exit=0'))

# 13 imports
ma, md = jl(A / '13_imports.json'), jl(D / '13_imports.json')
item('13 todos os módulos e scripts importam (os de antes menos os removidos)',
     sorted(set(ma) - REMOVIDOS) == sorted(md) and all(v == 'ok' for v in md.values()), f'{len(ma)} × {len(md)}')

print()
print('RESULTADO:', 'tudo igual no que é funcional (diferenças só as esperadas)' if not falhas else
      f'{len(falhas)} diferença(s): ' + '; '.join(falhas))
sys.exit(1 if falhas else 0)
