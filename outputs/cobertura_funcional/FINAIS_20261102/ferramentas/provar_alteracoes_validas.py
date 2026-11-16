"""Controles positivos: refatorações legítimas não devem ser bloqueadas pelo avaliador.

Executar na imagem Docker, com o checkout limpo, após os controles negativos.
Não executa SAST nem gera patches com LLM. Recusa sobrescrever resultados.
"""
import base64
import hashlib
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from scripts.experimento.validar_controles_cobertura import conferir_checkout
from pipeline.etapas.e06_aplicacao.worktrees import reservar_execucao
from pipeline.etapas.e02_catalogo.catalogo import carregar
from pipeline.etapas.e07_validacao import cobertura
from pipeline.etapas.e07_validacao.execucao_cobertura import executar_grupo


def jwt_replacements(source):
    import re
    rows = []
    for token in re.findall(r"'(eyJ[A-Za-z0-9_.-]+)'", source):
        header, payload, _ = token.split('.')
        decode = lambda data: json.loads(base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)))
        expression = "[btoa(JSON.stringify(" + json.dumps(decode(header)) + ")), btoa(JSON.stringify(" + json.dumps(decode(payload)) + ")), 'fixture'].join('.')"
        rows.append(("'" + token + "'", expression))
    if not rows:
        raise ValueError('Fixture JWT original ausente')
    return rows


def main():
    reservar_execucao(ROOT)
    wt = ROOT / 'workspace/wt-1'
    catalogo = carregar(ROOT / 'outputs/catalogos/ampliado_v1/catalogo_issues.json')
    conferir_checkout(wt, catalogo.commit)
    revisao = ROOT / 'config/cobertura_funcional_v6.yaml'
    mapa = ROOT / 'config/mapa_testes_relacionados_v7.yaml'
    data = cobertura.carregar(revisao, mapa, wt, catalogo)
    output = Path(__file__).resolve().parent.parent / 'alteracoes_validas'
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    for label, file in [('guard_jwt_gerado', 'frontend/src/app/app.guard.spec.ts'),
                        ('ip_jwt_gerado', 'frontend/src/app/last-login-ip/last-login-ip.component.spec.ts')]:
        cases.append((label, file, ['frontend_contracts', 'frontend_spec_integrity'], jwt_replacements((wt / file).read_text())))
    cases.append(('checksum_sha256', 'Gruntfile.js', ['grunt_artifacts'], [
        ("crypto.createHash('md5')", "crypto.createHash('sha256')"), ("file + '.md5'", "file + '.sha256'")]))
    template = (wt / 'views/promotionVideo.pug').read_text()
    split = next(line.strip() for line in template.splitlines() if line.strip().startswith('var splitted = '))
    cases.append(('subtitle_split_literal', 'views/promotionVideo.pug', ['video_parser'], [
        (split, "var splitted = lines[i].split('-->').map(function(part) { return part.trim(); });")]))
    report = {'schema_versao': '1.0', 'tipo': 'controles_positivos_alteracoes_validas', 'status': 'parcial',
              'commit_alvo': catalogo.commit, 'chamadas_llm': 0,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'cobertura': cobertura.identidade(data, revisao, mapa), 'controles': []}
    healthy = {}
    lock = threading.Lock()
    try:
        for label, file, groups, replacements in cases:
            for gid in groups:
                if gid not in healthy:
                    healthy[gid] = executar_grupo(wt, gid, data['grupos'][gid], output / ('original_' + gid), lock_api=lock)
                    if not healthy[gid]['comparavel'] or healthy[gid]['falhos']:
                        raise ValueError('Grupo original não aprovado: ' + gid)
            conferir_checkout(wt, catalogo.commit)
            source = cobertura.interno(wt, file)
            original = source.read_bytes()
            changed = original.decode()
            for before, after in replacements:
                if changed.count(before) != 1:
                    raise ValueError('Âncora positiva ausente/ambígua: ' + label)
                changed = changed.replace(before, after)
            changed = changed.encode()
            source.write_bytes(changed)
            try:
                selection = cobertura.selecionar(data, [file], wt)
                if not selection['suficiente']:
                    raise ValueError('Alteração válida indevidamente bloqueada pela seleção: ' + str(selection['motivos']))
                results = {gid: executar_grupo(wt, gid, data['grupos'][gid], output / label / gid, lock_api=lock) for gid in groups}
            finally:
                if source.read_bytes() != changed:
                    raise RuntimeError('Alteração desconhecida; restauração recusada')
                source.write_bytes(original)
            conferir_checkout(wt, catalogo.commit)
            accepted = all(result['comparavel'] and not result['falhos'] for result in results.values())
            report['controles'].append({'id': label, 'arquivo': file, 'grupos': groups,
                'original_sha256': hashlib.sha256(original).hexdigest(), 'alterado_sha256': hashlib.sha256(changed).hexdigest(),
                'selecao_suficiente': selection['suficiente'], 'aprovado': accepted,
                'restaurado': source.read_bytes() == original})
            print('Alteração válida', label, 'aprovada:', accepted, flush=True)
            if not accepted:
                raise ValueError('Uma alteração válida foi reprovada; consulte seus resultados')
        report['status'] = 'concluido'
    finally:
        report['artefatos_sha256'] = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(output.rglob('*')) if p.is_file()}
        (output / 'controles_positivos.json').write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    main()
