"""Controles sintéticos: nenhum scan, teste do alvo ou chamada à LLM."""
import copy
from dataclasses import replace
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from pipeline.sast.comparacao import chave, comparar as v1
from pipeline.sast.comparacao_v2 import comparar, intervalo, chamada
from pipeline.sast.semgrep_client import Finding, ScanResultado
from pipeline.painel.controller import resumo_tentativa
from pipeline.metrics.loader import _validar_contrato
from pipeline.validation.components import componentes
from pipeline.metrics.calculator import indices


def finding(text, focus, occurrence=0, rule='test.rule'):
    start = [m.start() for m in re.finditer(re.escape(focus), text)][occurrence]
    end = start+len(focus)
    def coord(n):
        return text[:n].count('\n')+1, len(text[:n].rsplit('\n',1)[-1].encode())+1
    sl, sc = coord(start); el, ec = coord(end)
    return Finding(rule, 'a.ts', sl, el, 'INFO', '', (), (), '', '', '',
                   start_col=sc, end_col=ec, start_offset=len(text[:start].encode()),
                   end_offset=len(text[:end].encode()))


def scan(findings, diagnostics=(), fail=None):
    return ScanResultado(findings, list(diagnostics), '1.177.0', fail)


def ast(text, scope='["function:f"]'):
    # Fixture propositalmente pequena, não é o parser de produção.
    tokens = []
    for m in re.finditer(r'//[^\n]*|[A-Za-z_]+|[^\s]', text):
        if not m.group().startswith('//'):
            tokens.append({'texto':m.group(), 'inicio':len(text[:m.start()].encode()),
                           'fim':len(text[:m.end()].encode())})
    calls = []
    for m in re.finditer(r'sink\(([^()]*)\)', text):
        calls.append({'inicio':len(text[:m.start()].encode()), 'fim':len(text[:m.end()].encode()),
                      'callee_inicio':len(text[:m.start()].encode()), 'callee_fim':len(text[:m.start()+4].encode()),
                      'callee':'sink', 'escopo':scope, 'aridade':1,
                      'argumentos':[[len(text[:m.start(1)].encode()), len(text[:m.end(1)].encode())]]})
    return {'tokens':tokens, 'chamadas':calls, 'escopos':[scope]}


def provider(path, a, b):
    return {'antes':ast(a.decode()), 'depois':ast(b.decode()), 'versao':'fixture'}


def compare(a, b, before, after, **kwargs):
    return comparar(scan(before), scan(after), chave(before[0]), {'a.ts':(a.encode(),b.encode())},
                    estrutura=kwargs.pop('estrutura', provider), **kwargs)


class ComparatorV2Tests(unittest.TestCase):
    def test_comment_outside_finding_does_not_hide_retained_occurrence(self):
        a='function f(){\n sink(x); // marcador antigo\n sink(y);\n}\n'
        b='function f(){\n sink(x);\n}\n'
        x,y=finding(a,'sink(x)'),finding(a,'sink(y)'); after=finding(b,'sink(x)')
        old=v1(scan([y,x]),scan([after]),chave(y),{'a.ts':(a.encode(),b.encode())})
        self.assertIsNone(old['R'])
        r=compare(a,b,[y,x],[after])
        self.assertEqual((r['R'],r['M']),(1,1))
        self.assertEqual(len(r['pares']),1)

    def test_rewritten_argument_with_same_unique_sink_is_persistent(self):
        a='function f(){\n sink(untrusted);\n}\n'
        b='function f(){\n const checked = validate();\n sink(checked);\n}\n'
        r=compare(a,b,[finding(a,'untrusted')],[finding(b,'checked',1)])
        self.assertEqual((r['R'],r['M']),(0,1))
        self.assertEqual(r['pares'][0]['metodo'],'chamada_unica_no_escopo')

    def test_multiple_calls_not_guessed_by_count(self):
        a='function f(){ sink(a); sink(b); }\n'
        b='function f(){ sink(c); sink(d); }\n'
        r=compare(a,b,[finding(a,'sink(a)')],[finding(b,'sink(c)')])
        self.assertEqual((r['R'],r['M']),(None,None))
        self.assertTrue(r['motivos_indeterminacao'])

    def test_other_function_does_not_match(self):
        a='function f(){ sink(before); }\n';b='function g(){ sink(after); }\n'
        def contexts(path,a,b):
            return {'antes':ast(a.decode(),'["f"]'),'depois':ast(b.decode(),'["g"]')}
        r=compare(a,b,[finding(a,'before')],[finding(b,'after')],estrutura=contexts)
        self.assertIsNone(r['R'])

    def test_new_rule_is_new_and_removed_target_is_removed(self):
        a='sink(a);\n';b='sink(b);\n'
        r=compare(a,b,[finding(a,'sink(a)')],[finding(b,'sink(b)',rule='new.rule')])
        self.assertEqual((r['R'],r['M']),(1,0))

    def test_duplicate_findings_are_not_silently_deduplicated(self):
        a='function f(){ sink(a); }\n';b='function f(){ sink(b); }\n'
        f=finding(a,'sink(a)');g=finding(b,'sink(b)')
        r=compare(a,b,[f,f],[g])
        self.assertEqual((r['R'],r['M']),(None,None))
        self.assertEqual(len(r['ambiguos'][0]['antes']),2)

    def test_parser_unavailable_preserves_v1_and_explains_ambiguity(self):
        a='sink(a);\n';b='sink(b);\n'
        def fail(*args):raise OSError('parser indisponível')
        r=compare(a,b,[finding(a,'sink(a)')],[finding(b,'sink(b)')],estrutura=fail)
        self.assertEqual((r['R'],r['M']),(None,None))
        self.assertIn('a.ts',r['falhas_contexto'])

    def test_utf8_crlf_and_conflicting_offsets(self):
        text='// ação\r\nsink(x);\r\n';f=finding(text,'x')
        lo,hi=intervalo(f,text.encode());self.assertEqual(text.encode()[lo:hi],b'x')
        with self.assertRaises(ValueError):intervalo(replace(f,start_offset=lo+1),text.encode())
        with self.assertRaises(ValueError):intervalo(replace(f,start_col=999),text.encode())

    def test_invalid_offset_also_invalidates_line_pairing(self):
        a='sink(x);\n';b='// nova linha\n'+a;f=finding(a,'x');g=replace(finding(b,'x'),start_offset=0)
        r=compare(a,b,[f],[g])
        self.assertEqual((r['R'],r['M']),(None,None))
        self.assertIn('a.ts',r['arquivos_inconclusivos'])

    def test_duplicate_scopes_and_arity_are_part_of_identity(self):
        data=ast('sink(x)')
        span=(5,6)
        self.assertIsNotNone(chamada(span,data))
        data['escopos']*=2
        self.assertIsNone(chamada(span,data))
        a=ast('sink(x)');b=copy.deepcopy(a);b['chamadas'][0]['aridade']=2
        self.assertNotEqual(chamada(span,a),chamada(span,b))

    def test_parsing_and_timeout_still_prevent_positive_results(self):
        text='sink(x);\n';f=finding(text,'x');error={'path':'a.ts','type':'Syntax'}
        for before,after in ((scan([f],[error]),scan([])),(scan([f]),scan([],fail='timeout'))):
            r=comparar(before,after,chave(f),{'a.ts':(text.encode(),b'')},estrutura=provider)
            self.assertEqual((r['R'],r['M']),(None,None))
            self.assertEqual(r['motivos_indeterminacao'][0]['codigo'],'cobertura_sast_insuficiente')

    def test_preexisting_unmodified_parsing_remains_limited(self):
        text='sink(x);\n';f=finding(text,'x');error={'path':'other.ts','type':'Syntax'}
        r=comparar(scan([f],[error]),scan([f],[error]),chave(f),{})
        self.assertEqual((r['R'],r['M']),(0,1));self.assertEqual(r['cobertura_limitada'],[error])

    def test_panel_keeps_reason_and_functional_failure_is_not_acceptance(self):
        reasons=[{'campo':'R','descricao':'Pareamento ambíguo','codigo':'ocorrencia_nao_pareada'}]
        row={'classificacao_final':'indeterminada_sast','motivos_indeterminacao':reasons,'versao_comparador':'ocorrencias_contexto_v2'}
        self.assertEqual(resumo_tentativa(row)['motivos_indeterminacao'],reasons)
        measured=indices([{'R':1,'F_criterio':0,'M':1,'classificacao_criterio':'rejeitada',
                           'status_aplicacao':'aplicado','testes_falhos_d_criterio':[]}],'criterio')
        self.assertEqual((measured['TRI'],measured['TRV'],measured['aceitas']),(1,0,0))
        self.assertIn('src/pipeline/sast/estrutura.cjs',componentes())


if __name__ == '__main__':unittest.main()
