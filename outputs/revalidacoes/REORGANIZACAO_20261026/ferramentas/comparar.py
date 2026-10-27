"""Compara as fotos 'antes' e 'depois' da reorganização. Sai com código 1 se algo funcional mudou."""
import filecmp
import json
import re
import sys
from pathlib import Path

base = Path(sys.argv[1])
A, D = base / 'antes', base / 'depois'
falhas = []


def item(nome, ok, detalhe=''):
    print(f"{'OK   ' if ok else 'FALHA'} {nome}" + (f' — {detalhe}' if detalhe else ''))
    if not ok:
        falhas.append(nome)


def ler(p):
    return (p).read_text(encoding='utf-8', errors='replace')


# 01 identidade científica
item('01 identidade científica (componentes, cobertura, prompts, RAG, perfis, catálogo, referência Docker)',
     json.loads(ler(A / '01_identidade.json')) == json.loads(ler(D / '01_identidade.json')))


# 02 arquivos
def inventario(p):
    out = {}
    for linha in ler(p).splitlines():
        h, _, caminho = linha.partition('  ')
        out[caminho] = h
    return out


ia, idp = inventario(A / '02_arquivos.txt'), inventario(D / '02_arquivos.txt')
removidos = sorted(set(ia) - set(idp))
novos = sorted(set(idp) - set(ia))
alterados = sorted(c for c in set(ia) & set(idp) if ia[c] != idp[c])
por_hash_novo = {}
for c in novos:
    por_hash_novo.setdefault(idp[c], []).append(c)
movidos = [(c, por_hash_novo[ia[c]][0]) for c in removidos if ia[c] in por_hash_novo]
movidos_origem = {a for a, _ in movidos}
movidos_destino = {n for _, n in movidos}
print(f'      arquivos: {len(movidos)} movidos sem alteração, {len(set(novos) - movidos_destino)} novos/alterados em local novo, '
      f'{len(set(removidos) - movidos_origem)} removidos sem destino idêntico, {len(alterados)} alterados no lugar')
for c in alterados:
    print(f'        alterado: {c}')
for c in sorted(set(novos) - movidos_destino):
    print(f'        novo: {c}')
for c in sorted(set(removidos) - movidos_origem):
    print(f'        removido (conteúdo mudou ou saiu): {c}')
permitido = re.compile(r'(\.md$|^src/pipeline/painel/server\.py$|^\.env\.example$)')
fora = [c for c in alterados + sorted(set(novos) - movidos_destino) if not permitido.search(c)]
item('02 só documentos (.md), o caminho da interface em painel/server.py e um comentário do .env.example '
     'mudaram de conteúdo', not fora, ', '.join(fora))
oa, od = inventario(A / '02_outputs.txt'), inventario(D / '02_outputs.txt')
extra = sorted(set(od) - set(oa))
item('02b outputs/ intocado (só o índice novo)', {k: v for k, v in od.items() if k != 'outputs/README.md'} == oa
     and extra in ([], ['outputs/README.md']), ', '.join(extra))


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
    return res, re.search(r'^Ran (\d+) tests', ler(p), re.M), ler(p).strip().splitlines()[-1]


ta, ra, ea = testes(A / '03_testes.txt')
td, rd, ed = testes(D / '03_testes.txt')
item('03 testes Python: mesmos testes, mesmos resultados', ta == td and ra and rd and ra.group(1) == rd.group(1) and ea == ed,
     f'antes {ra.group(1) if ra else "?"} ({ea}), depois {rd.group(1) if rd else "?"} ({ed})')

# 04 regras
item('04 testes das regras Semgrep', ler(A / '04_regras.txt').splitlines()[-3:] == ler(D / '04_regras.txt').splitlines()[-3:])


def diff_dir(x, y):
    dif = []

    def rec(c):
        dif.extend(str(Path(c.left).relative_to(x) / f) for f in c.diff_files + c.left_only + c.right_only)
        for sub in c.subdirs.values():
            rec(sub)
    rec(filecmp.dircmp(x, y))
    return dif


# Normalização das execuções: remove SOMENTE medições de tempo, nomes temporários, a cópia de trabalho
# sorteada para cada tentativa e hashes calculados sobre arquivos que contêm esses itens.
REGRAS = [
    'bloco "time" do Semgrep (segundos, memória, arquivos lentos, regras que estouraram tempo)',
    'campos de duração e horário (duracao*, tempos*, espera*, inicio*, fim*, *_s)',
    'campo "worktree" (qual das 4 cópias executou a tentativa)',
    'hashes derivados desses arquivos (artefatos_sha256, fontes_sha256, evidencia_sha256, baseline_sha256)',
    'em textos: pasta temporária /tmp/tcc_cobertura_*, milissegundos dos testes, atributos time= do JUnit, wt-N,\n'
    '          hostname do JUnit (ID do container, sorteado pelo Docker a cada execução)',
]
VOLATEIS = re.compile(r'^(duracao|tempos?_|espera|inicio|fim)|_s$|^worktree$|timestamp', re.I)
DERIVADOS = {'artefatos_sha256', 'fontes_sha256', 'evidencia_sha256', 'baseline_sha256', 'time'}


def norm_str(t):
    t = re.sub(r'/tmp/tcc_cobertura_[A-Za-z0-9_]+', '/tmp/<tmp>', t)
    t = re.sub(r'\(\d+(\.\d+)?ms\)', '(<ms>)', t)
    t = re.sub(r'(time|duration_ms)(=| )"?[0-9.]+"?', r'\1=<t>', t)
    t = re.sub(r'wt-\d+', 'wt-N', t)
    t = re.sub(r'hostname="[0-9a-f]+"', 'hostname=<container>', t)
    return t


def limpar(o):
    if isinstance(o, dict):
        return {k: limpar(v) for k, v in o.items() if not VOLATEIS.search(k) and k not in DERIVADOS}
    if isinstance(o, list):
        return [limpar(v) for v in o]
    if isinstance(o, str):
        return norm_str(o)
    return o


def comparar_pasta(x, y):
    """Compara duas pastas de execução após a normalização. Devolve (arquivos, diferentes)."""
    ax = {p.relative_to(x) for p in x.rglob('*') if p.is_file()}
    ay = {p.relative_to(y) for p in y.rglob('*') if p.is_file()}
    dif = [f'só de um lado: {p}' for p in sorted(ax ^ ay)]
    for rel in sorted(ax & ay):
        s = str(rel)
        pa, pb = x / rel, y / rel
        if pa.read_bytes() == pb.read_bytes() or s.endswith('.log'):
            continue  # logs de console têm horários
        if s.endswith('.json'):
            igual = limpar(json.loads(ler(pa))) == limpar(json.loads(ler(pb)))
        elif s.endswith('.jsonl'):
            ka = sorted(json.dumps(limpar(json.loads(l)), sort_keys=True) for l in ler(pa).splitlines() if l.strip())
            kb = sorted(json.dumps(limpar(json.loads(l)), sort_keys=True) for l in ler(pb).splitlines() if l.strip())
            igual = ka == kb
        elif s.endswith('.csv'):
            import csv, io
            def tab(t):
                linhas = list(csv.DictReader(io.StringIO(t)))
                out = []
                for r in linhas:
                    q = {}
                    for k, v in r.items():
                        if VOLATEIS.search(k) or k in DERIVADOS:
                            continue
                        try:
                            v = json.dumps(limpar(json.loads(v)), sort_keys=True)
                        except (ValueError, TypeError):
                            v = norm_str(v or '')
                        q[k] = v
                    out.append(json.dumps(q, sort_keys=True))
                return sorted(out)
            igual = tab(ler(pa)) == tab(ler(pb))
        else:
            igual = norm_str(ler(pa)) == norm_str(ler(pb))
        if not igual:
            dif.append(s)
    return len(ax), dif


print('      normalização aplicada às execuções (só o que muda a cada rodada, sem relação com resultado):')
for r in REGRAS:
    print('        - ' + r)
for nome in ('05_preflight', '05_preflight_METRICAS', '10_dryrun', '10_dryrun_METRICAS'):
    n, dif = comparar_pasta(A / nome, D / nome)
    item(f'{nome}: {n} arquivos iguais após a normalização', not dif, f'{len(dif)} diferentes: ' + ', '.join(dif[:6]))
for nome in ('05_preflight/prompts', '10_dryrun/prompts', '10_dryrun/respostas_llm', '10_dryrun/patches',
             '10_dryrun/codigos_corrigidos', '10_dryrun/comparacoes'):
    dif = diff_dir(A / nome, D / nome)
    item(f'{nome}: idênticos byte a byte (sem normalização)', not dif, ', '.join(dif[:5]))
item('05 preflight terminou com sucesso nas duas', ler(A / '05_preflight.log').strip().endswith('exit=0') and ler(D / '05_preflight.log').strip().endswith('exit=0'))
item('10 dry-run terminou com sucesso nas duas', ler(A / '10_dryrun.log').strip().endswith('exit=0') and ler(D / '10_dryrun.log').strip().endswith('exit=0'))
CAMPOS = ('caso_id', 'estrategia_prompt', 'R', 'F', 'M', 'F_criterio', 'F_marcador', 'F_sem_separacao',
          'classificacao_final', 'status_aplicacao', 'hash_prompt', 'tier_falha')


def chave(p):
    return sorted(tuple(str(json.loads(l).get(c)) for c in CAMPOS) for l in ler(p).splitlines() if l.strip())


ra = chave(A / '10_dryrun/resultados_consolidados/execucoes.jsonl')
rd = chave(D / '10_dryrun/resultados_consolidados/execucoes.jsonl')
item(f'10 dry-run: as {len(ra)} tentativas têm os mesmos R, F, M, classificação, aplicação e hash do prompt', ra == rd)

# 06 métricas oficiais
item('06 reconsolidação da campanha oficial idêntica ao arquivado (antes e depois)',
     ler(A / '06_diff_com_arquivado.txt').strip() == 'diff_exit=0' and ler(D / '06_diff_com_arquivado.txt').strip() == 'diff_exit=0')

# 07, 08, 12
item('07 comandos montados pelo executar.py', ler(A / '07_executar.txt') == ler(D / '07_executar.txt'))
item('08 Makefile (make -n de todos os alvos)', ler(A / '08_make.txt') == ler(D / '08_make.txt'))
item('12 conferência da referência Docker', ler(A / '12_referencia.txt') == ler(D / '12_referencia.txt'))

# 09 painel
dif = diff_dir(A / '09_painel', D / '09_painel')
item('09 painel: páginas e API idênticas', not dif, ', '.join(dif))

# 11 links
import os


def links(arq):
    t = ler(arq)
    quebrados = sorted(l.strip() for l in t.split('links para fora')[0].splitlines()[1:] if l.strip())
    raiz = base.resolve().parent.parent
    externos = []
    for l in t.splitlines():
        m = re.match(r'\s+externo: (\S+) -> (\S+)', l)
        if m:
            externos.append(os.path.normpath(os.path.join(str(raiz), os.path.dirname(m.group(1)), m.group(2))))
    return quebrados, sorted(externos)


qa, ea = links(A / '11_links.txt')
qd, ed = links(D / '11_links.txt')
item('11 nenhum link interno quebrado na documentação', not qd, f'antes {len(qa)}, depois {len(qd)}: {qd[:5]}')
item('11 links externos (fora do repositório) apontam para os mesmos destinos', ea == ed,
     f'{len(ea)} antes, {len(ed)} depois')

print()
print('RESULTADO:', 'tudo igual no que é funcional' if not falhas else f'{len(falhas)} diferença(s): ' + '; '.join(falhas))
sys.exit(1 if falhas else 0)
