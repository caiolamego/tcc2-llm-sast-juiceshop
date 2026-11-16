"""Repetição experimental; evidência incompleta retorna ao caminho amplo."""
import html
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET


def executados(xml, wt):
    out = []
    def visitar(node, suites):
        for child in node:
            if child.tag == 'testsuite':
                visitar(child, suites+[html.unescape(child.get('name',''))])
            elif child.tag == 'testcase' and child.find('skipped') is None:
                file = child.get('file','')
                try: file = Path(file).resolve().relative_to(wt.resolve()).as_posix()
                except ValueError: pass
                out.append(file+' :: '+' > '.join(suites+[html.unescape(child.get('name',''))]))
    visitar(ET.parse(xml).getroot(), [])
    return out


def repetir_seletivo(primeira, wt, timeout_s, env, base):
    from pipeline.etapas.e07_validacao.camadas import cmd_testes, SETUP_API, _uma_rodada
    esperados = primeira.testes_falhos_novos
    info = {'politica':'seletiva-experimental','esperados':esperados,'fallback':None}
    arquivos, nomes = set(), []
    for ident in esperados:
        arq, sep, nome = ident.partition(' :: ')
        path = (wt/arq).resolve()
        if (not sep or not arq.startswith('test/api/') or '..' in Path(arq).parts
                or not path.is_relative_to(wt.resolve()) or not path.is_file() or not nome):
            info['fallback']='identidade_invalida'
            return None, info
        arquivos.add(arq)
        nomes.append(nome.replace(' > ', ' '))
    if not nomes or len(set(esperados)) != len(esperados):
        info['fallback']='selecao_vazia_ou_ambigua'
        return None, info
    with tempfile.TemporaryDirectory(prefix='junit_T4_SELETIVO_') as tmp:
        xml = Path(tmp)/'resultado.xml'
        cmd = cmd_testes(SETUP_API, sorted(arquivos), xml)
        # Suites-pai precisam ser selecionadas para seus filhos chegarem a executar.
        parents = set()
        for ident in esperados:
            partes = ident.split(' :: ',1)[1].split(' > ')
            parents.update(' '.join(partes[:i]) for i in range(1,len(partes)))
        pattern = '^(?:'+'|'.join(re.escape(n) for n in sorted(set(nomes)|parents))+')$'
        cmd.insert(cmd.index('--test')+1, '--test-name-pattern='+pattern)
        resultado = _uma_rodada('T4', cmd, wt, timeout_s, env, xml, base)
        try: feitos = executados(xml, wt)
        except (OSError, ET.ParseError): feitos=[]
        info['executados'] = feitos
        if (resultado.motivo in ('timeout','comando_nao_encontrado','falha_sem_relatorio')
                or any(feitos.count(i) != 1 for i in esperados)):
            info['fallback']='cobertura_da_repeticao_incompleta'
            info['duracao_descartada_s']=resultado.duracao_s
            return None, info
        return resultado, info
