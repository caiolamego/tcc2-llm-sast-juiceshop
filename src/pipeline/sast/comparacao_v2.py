"""Pareamento por linhas, tokens únicos e chamadas únicas no mesmo escopo.

Identifica persistência de uma ocorrência sintática, não equivalência semântica
nem eficácia de uma correção. Ambiguidades e cobertura seguem a política v1.
"""
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import subprocess

from pipeline.sast.comparacao import comparar as comparar_v1, chave, ocorrencias
from pipeline.sast.estrutura import analisar

VERSAO = 'ocorrencias_contexto_v2'


def intervalo(f, source):
    """Semgrep usa colunas e offsets em bytes; fim exclusivo, inclusive CRLF."""
    lines = source.splitlines(keepends=True)
    def pos(line, col):
        if type(line) is not int or type(col) is not int or not 1 <= line <= len(lines):
            raise ValueError('Coordenada ausente/inválida')
        if not 1 <= col <= len(lines[line-1].rstrip(b'\r\n'))+1:
            raise ValueError('Coluna fora da linha')
        value = sum(map(len, lines[:line-1])) + col-1
        source[:value].decode('utf-8')  # Não aceitar coordenada no meio de um caractere.
        return value
    start, end = pos(f.start_line, f.start_col), pos(f.end_line, f.end_col)
    if start >= end:
        raise ValueError('Intervalo vazio/invertido')
    if f.start_offset is not None and f.start_offset != start:
        raise ValueError('Offset inicial contraditório')
    if f.end_offset is not None and f.end_offset != end:
        raise ValueError('Offset final contraditório')
    return start, end


def mapa_tokens(a, b):
    ta, tb = a['tokens'], b['tokens']
    aa, bb = [t['texto'] for t in ta], [t['texto'] for t in tb]
    blocks = []
    for block in SequenceMatcher(None, aa, bb, autojunk=False).get_matching_blocks():
        if block.size and ocorrencias(aa, aa[block.a:block.a+block.size]) == 1 and ocorrencias(bb, aa[block.a:block.a+block.size]) == 1:
            blocks.append(block)
    return blocks


def destino_tokens(span, a, b, blocks):
    start, end = span
    for block in blocks:
        old = a['tokens'][block.a:block.a+block.size]
        if not old or not old[0]['inicio'] <= start < end <= old[-1]['fim']:
            continue
        si = next((i for i, t in enumerate(old) if t['inicio'] <= start < t['fim']), None)
        ei = next((i for i, t in enumerate(old) if t['inicio'] < end <= t['fim']), None)
        if si is not None and ei is not None:
            new = b['tokens'][block.b:block.b+block.size]
            return (new[si]['inicio'] + start-old[si]['inicio'],
                    new[ei]['fim'] + end-old[ei]['fim'])
    return None


def chamada(span, ast):
    start, end = span
    candidates = []
    for c in ast['chamadas']:
        # A regra pode focar um argumento ou a chamada inteira. Não confundir
        # um argumento com outro ou aceitar somente a interseção de intervalos.
        if c['inicio'] == start and c['fim'] <= end <= c['fim']+1:
            candidates.append((c, 'chamada', 1))
        for n, (lo, hi) in enumerate(c['argumentos']):
            if lo <= start < end <= hi:
                candidates.append((c, f'argumento:{n}', 0 if (lo, hi) == span else 2))
    if not candidates:
        return None
    # O menor invólucro direto é o contexto mais específico do foco.
    c, role, _ = min(candidates, key=lambda x: (x[2], x[0]['fim']-x[0]['inicio']))
    key = (c['escopo'], c['callee'], c['aridade'])
    if c['escopo'] == '[]' or Counter(ast.get('escopos', []))[c['escopo']] != 1:
        return None
    # Conta todas as chamadas da fonte, inclusive as não sinalizadas pelo SAST.
    if sum((x['escopo'], x['callee'], x['aridade']) == key for x in ast['chamadas']) != 1:
        return None
    return (*key, role)


def foco_unico(span, ast):
    tokens = [t for t in ast['tokens'] if span[0] <= t['inicio'] < t['fim'] <= span[1]]
    if not tokens or tokens[0]['inicio'] != span[0] or tokens[-1]['fim'] != span[1]:
        return None
    text = [t['texto'] for t in tokens]
    if ocorrencias([t['texto'] for t in ast['tokens']], text) != 1:
        return None
    enclosing = [c for c in ast['chamadas'] if c['inicio'] <= span[0] < span[1] <= c['fim']]
    if not enclosing:
        return None
    scope = min(enclosing, key=lambda c: c['fim']-c['inicio'])['escopo']
    if scope != '[]' and Counter(ast.get('escopos', []))[scope] != 1:
        return None
    return (scope, hashlib.sha256(repr(text).encode()).hexdigest())


def ancora_chamada(signature, ast):
    key = signature[:3]
    calls = [c for c in ast['chamadas'] if (c['escopo'], c['callee'], c['aridade']) == key]
    if len(calls) != 1:
        return None
    return calls[0]['callee_inicio'], calls[0]['callee_fim']


def comparar(antes, depois, alvo, fontes, *, checkout=None, estrutura=None):
    result = comparar_v1(antes, depois, alvo, fontes)
    invalid = {}
    for side, scan in enumerate((antes, depois)):
        for finding in scan.findings:
            if finding.path in fontes:
                try:
                    intervalo(finding, fontes[finding.path][side])
                except (ValueError, UnicodeError) as exc:
                    invalid[finding.path] = str(exc)
    pairs = [dict(p, metodo='coordenadas_ou_bloco_linhas_v1') for p in result['pares']]
    used_a = Counter(tuple(p['antes']) for p in pairs)
    used_b = Counter(tuple(p['depois']) for p in pairs)
    groups = defaultdict(lambda: [[], []])
    for side, scan, used in ((0, antes, used_a), (1, depois, used_b)):
        for f in scan.findings:
            if used[chave(f)]:
                used[chave(f)] -= 1
            else:
                groups[(f.check_id, f.path)][side].append(f)
    structures, failures = {}, dict(invalid)
    for (rule, path), (a, b) in sorted(groups.items()):
        if not a or not b or path not in fontes:
            continue
        if path not in structures and path not in failures:
            try:
                if estrutura is None and checkout is None:
                    raise ValueError('Checkout do parser não informado')
                structures[path] = (estrutura or (lambda p, x, y: analisar(p, x, y, checkout)))(path, *fontes[path])
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                failures[path] = (str(exc)[:200] if isinstance(exc, ValueError) else
                                  type(exc).__name__ + ': contexto estrutural indisponível; mantido pareamento v1')
        data = structures.get(path)
        if not data:
            continue
        try:
            sa = [intervalo(f, fontes[path][0]) for f in a]
            sb = [intervalo(f, fontes[path][1]) for f in b]
            blocks = mapa_tokens(data['antes'], data['depois'])
        except (ValueError, UnicodeError, KeyError) as exc:
            failures[path] = str(exc)
            continue
        paired_a, paired_b = set(), set()
        for method in ('tokens_unicos', 'foco_tokens_unico', 'chamada_unica_no_escopo'):
            proposals = []
            for i, f in enumerate(a):
                if i in paired_a:
                    continue
                signature = foco_unico if method == 'foco_tokens_unico' else chamada
                evidence = (destino_tokens(sa[i], data['antes'], data['depois'], blocks)
                            if method == 'tokens_unicos' else signature(sa[i], data['antes']))
                if evidence is None:
                    continue
                candidates = [j for j in range(len(b)) if j not in paired_b and
                              (sb[j] if method == 'tokens_unicos' else signature(sb[j], data['depois'])) == evidence]
                if method == 'chamada_unica_no_escopo':
                    anchor = ancora_chamada(evidence, data['antes'])
                    mapped = destino_tokens(anchor, data['antes'], data['depois'], blocks) if anchor else None
                    lexical = foco_unico(anchor, data['antes']) if anchor else None
                    candidates = [j for j in candidates if
                                  (mapped is not None and ancora_chamada(chamada(sb[j], data['depois']), data['depois']) == mapped)
                                  or (lexical is not None and lexical == foco_unico(
                                      ancora_chamada(chamada(sb[j], data['depois']), data['depois']),data['depois']))]
                if len(candidates) == 1:
                    proposals.append((i, candidates[0], evidence))
            counts = Counter(j for _, j, _ in proposals)
            for i, j, evidence in proposals:
                if counts[j] == 1:
                    paired_a.add(i); paired_b.add(j)
                    pairs.append({'antes': list(chave(a[i])), 'depois': list(chave(b[j])),
                                  'metodo': method, 'evidencia': list(evidence)})
        groups[(rule, path)] = [[f for i, f in enumerate(a) if i not in paired_a],
                             [f for i, f in enumerate(b) if i not in paired_b]]
    removed, new, ambiguous = [], [], []
    for (rule, path), (a, b) in sorted(groups.items()):
        aa, bb = [list(chave(f)) for f in a], [list(chave(f)) for f in b]
        if aa and bb:
            ambiguous.append({'regra': rule, 'arquivo': path, 'antes': aa, 'depois': bb})
        else:
            removed.extend(aa); new.extend(bb)
    affected = set(result['arquivos_inconclusivos']) | set(invalid)
    old_errors = {e.get('path') or '*' for e in antes.diagnosticos}
    confirmed = [k for k in new if not {'*', k[1]} & (affected | old_errors)]
    uncertain = [k for k in new if k not in confirmed]
    r = 0 if any(p['antes'] == list(alvo) for p in pairs) else 1 if list(alvo) in removed else None
    if {'*', alvo[1]} & affected or any(e.get('path') == alvo[1] for e in antes.diagnosticos+depois.diagnosticos):
        r = None
    m = 0 if confirmed else None if ambiguous or affected or uncertain else 1
    reasons = []
    if r is None:
        reasons.append({'campo': 'R', 'codigo': 'cobertura_sast_insuficiente' if {'*', alvo[1]} & (affected | old_errors) else 'ocorrencia_nao_pareada',
                        'arquivo': alvo[1], 'descricao': 'Não foi possível comprovar a identidade ou a remoção do alerta alvo.'})
    if m is None:
        reasons.append({'campo': 'M', 'codigo': 'cobertura_sast_insuficiente' if affected or uncertain else 'pareamento_ambiguo',
                        'arquivos': sorted(affected | {g['arquivo'] for g in ambiguous}),
                        'descricao': 'Há alertas sem associação segura ou cobertura insuficiente para excluir novas ocorrências.'})
    result.update(versao_comparador=VERSAO, R=r, M=m, pares=pairs, removidos=removed,
                  novos=confirmed, possiveis_novos=uncertain, ambiguos=ambiguous,
                  novas_issues_qtd=len(confirmed),
                  possiveis_novas_issues_qtd=len(uncertain)+sum(len(g['depois']) for g in ambiguous),
                  comparacao_status='indeterminada' if r is None or m is None else 'conclusiva',
                  motivos_indeterminacao=reasons, falhas_contexto=failures,
                  arquivos_inconclusivos=sorted(affected),
                  parser_por_arquivo={p: {'versao': d.get('versao'), 'identidade': d.get('identidade')}
                                      for p, d in sorted(structures.items())})
    return result
