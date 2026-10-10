"""Classifica novo scan por evidencia exata historica ou revisao explicita.

Nao associa por proximidade. Mantem todos os findings, inclusive fora do escopo.
"""
import argparse
from collections import Counter
import csv
import fnmatch
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scan', type=Path, required=True)
    parser.add_argument('--worktree', type=Path, required=True)
    parser.add_argument('--saida', type=Path, required=True)
    parser.add_argument('--revisao', type=Path)
    args = parser.parse_args()
    if args.saida.exists():
        parser.error('Escolha saida nova para preservar revisoes')
    oldpath = ROOT / 'outputs/auditoria_sast/rodada12/matriz_desafios.json'
    old = json.loads(oldpath.read_text())
    scan = json.loads(args.scan.read_text())
    target = args.worktree.resolve()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip()
    assert commit == old['commit_alvo']
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=target, text=True).strip()
    assert scan['version'] == old['semgrep_versao']
    for path, digest in old['regras_locais_sha256'].items():
        assert sha(ROOT / path) == digest, f'Regra local alterada: {path}'
    known = {a['regra'] for a in old['alertas']}
    exclusions = [s.strip() for s in (ROOT / 'config/semgrepignore').read_text().splitlines() if s.strip() and not s.startswith('#')]
    def outside(path):
        return any((path.startswith(p) or '/' + p in '/' + path) if p.endswith('/') else fnmatch.fnmatch(path, p) or fnmatch.fnmatch(Path(path).name, p) for p in exclusions)
    index = {}
    for a in old['alertas']:
        index.setdefault((a['regra'], a['arquivo'], a['inicio'], a['fim']), []).append(a)
    reviews = json.loads(args.revisao.read_text()) if args.revisao else []
    review_index = {(r['regra'], r['arquivo'], r['inicio'], r['fim']): r for r in reviews}
    assert len(review_index) == len(reviews)
    used = set()
    alerts = []
    keys = {d['key'] for d in old['desafios']}
    for number, result in enumerate(scan['results'], 1):
        path = Path(result['path'])
        if path.is_absolute():
            rel = str(path.relative_to(target))
        else:
            rel = str(path).removeprefix('./')
        rule = result['check_id']
        # Semgrep prefixa IDs locais quando --no-rewrite-rule-ids e omitido.
        candidates = [r for r in known if r.startswith('tcc.') and rule.endswith('.' + r)]
        normalized = candidates[0] if len(candidates) == 1 else rule
        start, end = result['start']['line'], result['end']['line']
        assert 1 <= start <= end <= len((target / rel).read_text(errors='replace').splitlines())
        key = normalized, rel, start, end
        a = dict(numero=number, regra_original=rule, regra=normalized, arquivo=rel, inicio=start, fim=end,
                 status='inconclusivo', desafios=[], motivo='Sem revisao conclusiva; nao contado como confirmado.', referencias_historicas=[])
        matches = index.get(key, [])
        signatures = {json.dumps(x['triagem'], sort_keys=True) for x in matches}
        if outside(rel):
            a.update(status='fora_escopo', motivo='Arquivo excluido pelo escopo historico do experimento; mantido na contagem bruta, nao nos desafios.')
        elif len(signatures) == 1:
            triage = matches[0]['triagem']
            a.update(status=triage['status'], motivo=triage['motivo'], desafios=triage['desafios_confirmados'], referencias_historicas=[x['id'] for x in matches])
        elif matches:
            # Mesma classificacao/associacao com justificativas complementares.
            decisions = {(x['triagem']['status'], tuple(sorted(x['triagem']['desafios_confirmados']))) for x in matches}
            if len(decisions) == 1:
                status, challenges = decisions.pop()
                a.update(status=status, desafios=list(challenges), motivo=' | '.join(dict.fromkeys(x['triagem']['motivo'] or '' for x in matches)), referencias_historicas=[x['id'] for x in matches])
        if key in review_index:
            r = review_index[key]
            assert r['status'] in {'confirmado', 'falso_positivo', 'inconclusivo', 'fora_escopo'}
            assert set(r.get('desafios', [])) <= keys
            a.update(status=r['status'], desafios=r.get('desafios', []), motivo=r['motivo'])
            used.add(key)
        if a['status'] != 'confirmado':
            assert not a['desafios']
        alerts.append(a)
    assert used == set(review_index), 'Revisao sem finding correspondente'
    challenges = []
    for d in old['desafios']:
        linked = [a['numero'] for a in alerts if a['status'] == 'confirmado' and d['key'] in a['desafios']]
        challenges.append(dict(key=d['key'], nome=d['nome'], categoria=d['categoria'],
                               confirmacao='confirmado' if linked else 'nao_confirmado_neste_scan', alertas=linked,
                               confirmacao_historica=d['confirmacao']))
    assert len(challenges) == len({d['key'] for d in challenges}) == 113
    counts = dict(Counter(a['status'] for a in alerts))
    confirmed = {d['key'] for d in challenges if d['confirmacao'] == 'confirmado'}
    previous = {d['key'] for d in old['desafios'] if d['confirmacao'] == 'confirmado'}
    summary = dict(commit_alvo=commit, semgrep_versao=scan['version'], alertas_brutos=len(alerts), triagem=counts,
                   desafios_confirmados=len(confirmed), desafios_total=113,
                   novos_desafios_confirmados=sorted(confirmed - previous), anteriores_nao_reencontrados=sorted(previous - confirmed),
                   avisos=scan.get('errors', []), scan_sha256=sha(args.scan), matriz_historica_sha256=sha(oldpath),
                   revisao_sha256=sha(args.revisao) if args.revisao else None,
                   criterio='Mesma regra normalizada, arquivo e intervalo no commit limpo, ou revisao explicita. Fora de escopo nao conta como FP. Confirmacoes condicionais historicas preservadas.')
    args.saida.mkdir(parents=True)
    for name, data in [('resumo', summary), ('alertas_classificados', alerts), ('matriz_desafios', challenges)]:
        (args.saida / (name + '.json')).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    for name, data in [('alertas_classificados', alerts), ('matriz_desafios', challenges)]:
        with (args.saida / (name + '.csv')).open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows({k: ';'.join(map(str,v)) if isinstance(v, list) else v for k,v in r.items()} for r in data)
    print(json.dumps({**summary, 'avisos': len(summary['avisos'])}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
