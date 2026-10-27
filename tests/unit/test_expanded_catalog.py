"""Contrato do catálogo ampliado: fixtures locais, sem rede, Semgrep ou LLM."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.experimento import gerar_catalogo_ampliado as c

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class ExpandedCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wt = self.root / 'alvo'
        self.wt.mkdir()
        self.source = self.wt / 'a.ts'
        self.source.write_bytes(b'one\r\ntwo\r\nthree\r\nfour\r\nfive\r\nsix\r\nseven\r\neight\r\n')
        self.git('init', '-q')
        self.commit()
        self.scan = {'version': '1.177.0', 'errors': [], 'results': []}
        self.classified = []
        for number, status in enumerate(c.STATUS, 1):
            filename = 'missing.ts' if status == 'fora_escopo' else 'a.ts'
            rule = 'tcc.example'
            self.scan['results'].append({'check_id': rule, 'path': '/origem/' + filename,
                'start': {'line': number, 'col': 1}, 'end': {'line': number, 'col': 2},
                'extra': {'severity': 'INFO', 'message': 'exemplo', 'metadata': {}}})
            self.classified.append({'numero': number, 'regra': rule, 'regra_original': rule,
                'arquivo': filename, 'inicio': number, 'fim': number, 'status': status,
                'desafios': [], 'referencias_historicas': [], 'motivo': 'justificativa'})
        self.paths = {role: self.root / (role + ('.yaml' if role.startswith('mapa_') else '.json')) for role in c.DEFAULTS}
        self.maps = {'mapa_cwe': {'CWE-89': 'SQLI'}, 'mapa_owasp': {'A03:2021': 'A05'}, 'mapa_rag': {'SQLI': 'injection', 'OUTRO': None}}
        self.save()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.wt), *args], stderr=subprocess.PIPE, text=True).strip()

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')

    def save(self):
        commit = self.git('rev-parse', 'HEAD')
        self.paths['scan'].write_bytes(c.serializar(self.scan))
        self.paths['classificacao'].write_bytes(c.serializar(self.classified))
        digest = c.sha(self.paths['scan'].read_bytes())
        counts = {s: sum(a['status'] == s for a in self.classified) for s in c.STATUS}
        summary = {'commit_alvo': commit, 'semgrep_versao': self.scan['version'], 'scan_sha256': digest,
                   'alertas_brutos': len(self.scan['results']), 'triagem': counts}
        manifest = {k: summary[k] for k in ('commit_alvo', 'semgrep_versao', 'scan_sha256')}
        manifest['findings'] = len(self.scan['results'])
        self.paths['resumo'].write_bytes(c.serializar(summary))
        self.paths['manifesto_scan'].write_bytes(c.serializar(manifest))
        for role, data in self.maps.items():
            self.paths[role].write_bytes(c.serializar(data))  # JSON é YAML válido.

    def build(self):
        return c.construir(c.carregar_fontes(self.paths), self.wt, '/origem')

    def test_inclusion_context_and_output_contract(self):
        artifacts, meta = self.build()
        cases = json.loads(artifacts['catalogo_issues.json'])
        exclusions = json.loads(artifacts['exclusoes.json'])
        self.assertEqual([a['classificacao_auditoria'] for a in cases], list(c.STATUS[:3]))
        self.assertEqual(len(exclusions), 1)
        self.assertNotIn('trecho', exclusions[0])
        self.assertNotIn('caso_id', exclusions[0])
        self.assertEqual(cases[0]['trecho'], 'one\r\ntwo\r\nthree\r\nfour\r\n')
        self.assertEqual(cases[0]['trecho_linha_inicio'], 1)
        for a in cases:
            self.assertTrue(a['elegivel'])
            self.assertIsNone(a['motivo_exclusao'])
            self.assertEqual(a['severidade'], 'INFO')
            self.assertEqual(a['categoria_rag'], 'generico')
            self.assertEqual(a['sigla_vuln'], 'OUTRO')
            self.assertEqual(a['cwe'], [])
            self.assertIsNone(a['owasp_2025'])
            self.assertNotIn('assinatura', a)
        for name, digest in meta['artefatos'].items():
            self.assertEqual(c.sha(artifacts[name]), digest)
        self.assertEqual(meta['contagens']['incluidos_sem_cwe'], 3)

    def test_maps_null_strings_and_owasp_priority(self):
        m = self.scan['results'][0]['extra']['metadata']
        m.update(cwe=['CWE-999: other', 'CWE-89: SQL', 'CWE-89'], owasp=['A03:2021 - Injection', 'A01:2025 - Access'])
        self.scan['results'][1]['extra']['metadata'].update(cwe='CWE-89: SQL', owasp='A03:2021 - Injection')
        self.scan['results'][2]['extra']['metadata'].update(cwe=None, owasp=None)
        self.save()
        artifacts, _ = self.build()
        cases = json.loads(artifacts['catalogo_issues.json'])
        self.assertEqual(cases[0]['cwe_ids'], ['CWE-999', 'CWE-89'])
        self.assertEqual(cases[0]['sigla_vuln'], 'SQLI')
        self.assertEqual(cases[0]['owasp_2025'], 'A01')
        self.assertEqual(cases[1]['owasp_2025'], 'A05')
        self.assertEqual(cases[1]['categoria_rag'], 'injection')

    def test_two_rules_same_location_and_duplicate_rejected(self):
        self.scan['results'][1]['start'] = copy.deepcopy(self.scan['results'][0]['start'])
        self.scan['results'][1]['end'] = copy.deepcopy(self.scan['results'][0]['end'])
        self.classified[1].update(inicio=1, fim=1, regra='tcc.other', regra_original='tcc.other')
        self.scan['results'][1]['check_id'] = 'tcc.other'
        self.save()
        self.assertEqual(len(json.loads(self.build()[0]['catalogo_issues.json'])), 3)
        self.classified[1].update(regra='tcc.example', regra_original='tcc.example')
        self.scan['results'][1]['check_id'] = 'tcc.example'
        self.save()
        with self.assertRaisesRegex(c.CatalogoErro, 'Identidade duplicada'):
            self.build()

    def test_short_id_collision(self):
        def collided(commit, a, r):
            return 'a' * 16 + str(a['numero']) * 48
        with patch.object(c, 'identidade', side_effect=collided), self.assertRaisesRegex(c.CatalogoErro, 'Colisão'):
            self.build()

    def test_reordering_and_map_change_preserve_identity(self):
        original = self.build()[0]['catalogo_issues.json']
        self.classified.reverse()
        self.save()
        self.assertEqual(original, self.build()[0]['catalogo_issues.json'])
        self.maps['mapa_rag']['OUTRO'] = 'outro_contexto'
        self.save()
        modified = self.build()[0]['catalogo_issues.json']
        self.assertNotEqual(original, modified)
        self.assertEqual([a['caso_id'] for a in json.loads(original)], [a['caso_id'] for a in json.loads(modified)])

    def test_prefix_and_relative_scan_path(self):
        self.scan['results'][0]['check_id'] = 'rules.rodada1.tcc.example'
        self.classified[0]['regra_original'] = 'rules.rodada1.tcc.example'
        self.scan['results'][0]['path'] = './a.ts'
        self.save()
        self.build()

    def test_invalid_associations(self):
        base = copy.deepcopy(self.classified)
        for field, value in [('numero', 2), ('numero', True), ('numero', 99), ('status', 'unknown'),
                             ('regra', 'other.rule'), ('regra_original', 'wrong'), ('arquivo', '../a.ts'),
                             ('arquivo', 'other.ts'), ('inicio', 8), ('desafios', 42)]:
            with self.subTest(field=field, value=value):
                self.classified = copy.deepcopy(base)
                self.classified[0][field] = value
                self.save()
                with self.assertRaises(c.CatalogoErro):
                    self.build()

    def test_invalid_metadata_and_positions(self):
        original = copy.deepcopy(self.scan)
        mutations = [lambda r: r['extra']['metadata'].update(cwe=[89]),
                     lambda r: r['extra'].update(severity=5),
                     lambda r: r['extra'].update(message=None),
                     lambda r: r['start'].update(col=0),
                     lambda r: r['start'].update(offset=-1),
                     lambda r: r['end'].update(offset=99999),
                     lambda r: r.update(path='/outro/a.ts'),
                     lambda r: r.update(path='/origem/../a.ts')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.scan = copy.deepcopy(original)
                mutation(self.scan['results'][0])
                self.save()
                with self.assertRaises(c.CatalogoErro):
                    self.build()

    def test_provenance_mismatches(self):
        for role, field, value in [('resumo', 'scan_sha256', 'wrong'), ('manifesto_scan', 'commit_alvo', '0' * 40),
                                   ('resumo', 'semgrep_versao', '0'), ('manifesto_scan', 'findings', 7),
                                   ('resumo', 'triagem', {'confirmado': 50})]:
            with self.subTest(role=role, field=field):
                self.save()
                data = json.loads(self.paths[role].read_text())
                data[field] = value
                self.paths[role].write_bytes(c.serializar(data))
                with self.assertRaises(c.CatalogoErro):
                    self.build()

    def test_wrong_or_dirty_checkout(self):
        expected = self.git('rev-parse', 'HEAD')
        with self.assertRaisesRegex(c.CatalogoErro, 'Commit'):
            c.conferir_checkout(self.wt, '0' * 40)
        self.source.write_text('changed')
        with self.assertRaisesRegex(c.CatalogoErro, 'modificado'):
            c.conferir_checkout(self.wt, expected)

    def test_missing_invalid_source_and_symlink(self):
        self.source.unlink()
        self.commit()
        self.save()
        with self.assertRaisesRegex(c.CatalogoErro, 'ausente'):
            self.build()
        self.source.write_bytes(b'\xff')
        self.commit()
        self.save()
        with self.assertRaisesRegex(c.CatalogoErro, 'UTF-8'):
            self.build()
        self.source.unlink()
        external = self.root / 'external.ts'
        external.write_text('x\n')
        self.source.symlink_to(external)
        self.commit()
        self.save()
        with self.assertRaisesRegex(c.CatalogoErro, 'fora do checkout'):
            self.build()

    def test_line_bounds_and_large_context(self):
        self.source.write_text('x\n')
        self.commit()
        self.save()
        with self.assertRaisesRegex(c.CatalogoErro, 'linhas fora'):
            self.build()
        self.source.write_text('x\n' * 251)
        self.commit()
        self.save()
        a = json.loads(self.build()[0]['catalogo_issues.json'])[0]
        self.assertEqual(a['modo_contexto'], 'janela_contexto')
        self.assertEqual(a['trecho'], 'x\n' * 4)

    def test_publication_and_determinism_different_checkouts(self):
        before = {p: c.sha(p.read_bytes()) for p in self.paths.values()}
        first, second = self.root / 'first', self.root / 'second'
        c.gerar(self.paths, self.wt, first, '/origem')
        other = self.root / 'outro-alvo'
        shutil.copytree(self.wt, other)
        c.gerar(self.paths, other, second, '/origem')
        self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()}, {p.name: p.read_bytes() for p in second.iterdir()})
        self.assertEqual(before, {p: c.sha(p.read_bytes()) for p in self.paths.values()})
        with self.assertRaisesRegex(c.CatalogoErro, 'Saída já existe'):
            c.gerar(self.paths, self.wt, first, '/origem')

    def test_lock_is_preserved_and_existing_empty_output_rejected(self):
        dest = self.root / 'out'
        lock = self.root / 'out.lock'
        lock.write_text('owner')
        with self.assertRaisesRegex(c.CatalogoErro, 'Lock existente'):
            c.gerar(self.paths, self.wt, dest, '/origem')
        self.assertEqual(lock.read_text(), 'owner')
        lock.unlink()
        dest.mkdir()
        with self.assertRaises(c.CatalogoErro):
            c.gerar(self.paths, self.wt, dest, '/origem')
        self.assertEqual(list(dest.iterdir()), [])

    def test_concurrent_destination_and_failed_write(self):
        dest = self.root / 'out'
        with self.assertRaisesRegex(c.CatalogoErro, 'durante'):
            c.publicar(dest, {'a.json': b'{}'}, dest.mkdir)
        self.assertEqual(list(dest.iterdir()), [])
        dest.rmdir()
        with patch.object(Path, 'write_bytes', side_effect=OSError('disco cheio')):
            with self.assertRaises(OSError):
                c.publicar(dest, {'a.json': b'{}'}, lambda: None)
        self.assertFalse(dest.exists())
        self.assertFalse((self.root / 'out.lock').exists())
        self.assertFalse(list(self.root.glob('.out-*')))

    def test_revalidation_aborts_publication(self):
        sources = c.carregar_fontes(self.paths)
        artifacts, meta = c.construir(sources, self.wt, '/origem')
        def change_source():
            self.source.write_text('changed')
            c.revalidar(sources, self.wt, meta)
        dest = self.root / 'out'
        with self.assertRaises(c.CatalogoErro):
            c.publicar(dest, artifacts, change_source)
        self.assertFalse(dest.exists())
        self.assertFalse((self.root / 'out.lock').exists())

    def test_revalidation_of_inputs(self):
        sources = c.carregar_fontes(self.paths)
        _, meta = c.construir(sources, self.wt, '/origem')
        self.paths['mapa_rag'].write_text('{}')
        with self.assertRaisesRegex(c.CatalogoErro, 'Fonte alterada'):
            c.revalidar(sources, self.wt, meta)

    def test_cli_outside_repository(self):
        cmd = [sys.executable, str(Path(c.__file__).resolve())]
        self.assertEqual(subprocess.run(cmd + ['--help'], cwd=self.root, capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(cmd, cwd=self.root, capture_output=True).returncode, 2)
        cmd += ['--worktree', str(self.wt), '--saida', str(self.root / 'cli-out'), '--raiz-scan', '/origem']
        for role in ('scan', 'classificacao', 'resumo', 'manifesto_scan'):
            cmd += ['--' + role.replace('_', '-'), str(self.paths[role])]
        r = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('Traceback', r.stderr)

    def test_hash_revalidation_even_when_git_ignores_working_changes(self):
        sources = c.carregar_fontes(self.paths)
        _, meta = c.construir(sources, self.wt, '/origem')
        self.git('update-index', '--assume-unchanged', 'a.ts')
        self.source.write_text('alterado')
        self.assertEqual(self.git('status', '--porcelain'), '')
        with self.assertRaisesRegex(c.CatalogoErro, 'Arquivo alterado'):
            c.revalidar(sources, self.wt, meta)

    def test_unknown_missing_severity_and_offsets(self):
        self.scan['results'][0]['extra'].pop('severity')
        self.scan['results'][1]['extra']['severity'] = 'LOW'
        self.scan['results'][2]['extra']['severity'] = 'FUTURE_LEVEL'
        self.save()
        self.assertEqual(self.build()[1]['contagens']['por_severidade'],
                         {'SEM_DADO': 1, 'LOW': 1, 'FUTURE_LEVEL': 1})
        self.scan['results'][0]['start']['offset'] = 4
        self.scan['results'][0]['end']['offset'] = 2
        self.save()
        with self.assertRaisesRegex(c.CatalogoErro, 'Offsets invertidos'):
            self.build()

    def test_malformed_inputs_and_missing_classification(self):
        self.paths['scan'].write_text('{invalid')
        with self.assertRaisesRegex(c.CatalogoErro, 'scan'):
            c.carregar_fontes(self.paths)
        self.save()
        self.classified.pop()
        self.save()
        with self.assertRaisesRegex(c.CatalogoErro, 'Contagem bruta'):
            self.build()

    def test_official_archive_reconciliation_without_checkout(self):
        f = c.carregar_fontes(c.DEFAULTS)
        pairs = c.validar_associacoes(f, '/tmp/tcc-juiceshop-audit')
        self.assertEqual(len(pairs), 124)
        self.assertEqual({s: sum(a['status'] == s for a, _ in pairs) for s in c.STATUS},
                         dict(confirmado=55, falso_positivo=21, inconclusivo=2, fora_escopo=46))
        keys = [c.identidade(f.dados['resumo']['commit_alvo'], a, r) for a, r in pairs]
        self.assertEqual(len(set(keys)), 124)


if __name__ == '__main__':
    unittest.main()
