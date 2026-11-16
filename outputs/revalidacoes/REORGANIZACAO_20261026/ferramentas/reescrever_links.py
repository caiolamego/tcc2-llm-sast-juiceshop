"""Corrige referências a arquivos movidos em documentos Markdown (fora de outputs/).

Uso: python3 reescrever_links.py <raiz> <mapa.json> <lista_antiga.txt> <versionados_antigos.txt> [--simular]
- mapa.json: {"caminho/antigo": "caminho/novo", ...} (arquivos ou pastas, relativos à raiz)
- lista_antiga.txt: arquivos existentes antes das mudanças (versionados e não versionados)
- versionados_antigos.txt: arquivos versionados antes das mudanças; só os .md deles são reescritos

Para cada .md: recalcula links relativos [texto](alvo) considerando a posição antiga e a
nova do próprio documento e do alvo; troca menções literais a caminhos antigos completos
(ex.: `docs/painel_local.md`) pelos novos. Mostra cada alteração.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import PurePosixPath

raiz, mapa_arq, lista_arq, versionados_arq = sys.argv[1:5]
SIMULAR = '--simular' in sys.argv[5:]
mapa = json.load(open(mapa_arq, encoding='utf-8'))
# Entradas só para localizar a posição antiga de um documento copiado (ex.: README antigo),
# sem redirecionar links de outros documentos nem trocar menções no texto.
somente_origem = {k: mapa.pop(k) for k in list(mapa.pop('_somente_origem', []))}
# Documentos históricos: só os links clicáveis são corrigidos; o texto (comandos, registros) fica como foi escrito.
somente_links = tuple(mapa.pop('_somente_links', []))
antigos = set(l.strip() for l in open(lista_arq, encoding='utf-8') if l.strip())
pastas_antigas = {str(p) for f in antigos for p in PurePosixPath(f).parents if str(p) != '.'}


def novo_de(antigo):
    """Caminho novo de um caminho antigo (arquivo ou pasta), ou o mesmo se não mudou."""
    for a, n in sorted(mapa.items(), key=lambda kv: -len(kv[0])):
        if antigo == a or antigo.startswith(a.rstrip('/') + '/'):
            return n + antigo[len(a):]
    return antigo


inverso = {}
for f in antigos:
    inverso[novo_de(f)] = f
for antigo, novo in somente_origem.items():
    inverso[novo] = antigo


def antigo_de(novo):
    return inverso.get(novo, novo)


def norm(p):
    return os.path.normpath(p).replace(os.sep, '/')


versionados = [l.strip() for l in open(versionados_arq, encoding='utf-8') if l.strip()]
atuais = sorted({novo_de(f) for f in versionados if f.endswith('.md')} | set(somente_origem.values()))
link = re.compile(r'(\[[^\]]*\]\()([^)\s]+)(\))')
total = 0
for doc_novo in sorted(atuais):
    if doc_novo.startswith(('outputs/', 'workspace/', '.cache/')) or not os.path.isfile(os.path.join(raiz, doc_novo)):
        continue
    doc_antigo = antigo_de(doc_novo)
    dir_antigo = str(PurePosixPath(doc_antigo).parent)
    dir_novo = str(PurePosixPath(doc_novo).parent)
    texto = open(os.path.join(raiz, doc_novo), encoding='utf-8').read()
    original = texto

    def trocar_link(m):
        alvo = m.group(2)
        if alvo.startswith(('http://', 'https://', 'mailto:', '#')):
            return m.group(0)
        caminho, sep, ancora = alvo.partition('#')
        if not caminho:
            return m.group(0)
        alvo_antigo = norm(os.path.join(dir_antigo, caminho))
        if alvo_antigo == '..' or alvo_antigo.startswith('../'):
            alvo_novo = alvo_antigo  # fora do repositório: mantém o mesmo destino real
        elif alvo_antigo not in antigos and alvo_antigo not in pastas_antigas:
            return m.group(0)  # já estava quebrado: não mexe
        else:
            alvo_novo = novo_de(alvo_antigo)
        rel = os.path.relpath(alvo_novo, dir_novo if dir_novo != '.' else '.').replace(os.sep, '/')
        if caminho.endswith('/') and not rel.endswith('/'):
            rel += '/'
        novo = rel + (sep + ancora if sep else '')
        return m.group(1) + novo + m.group(3)

    texto = link.sub(trocar_link, texto)
    if doc_novo.startswith(somente_links):
        mapa_texto = {}
    else:
        mapa_texto = mapa
    # Menções literais a caminhos completos antigos (fora de links já tratados). Só chaves com
    # "/" (caminhos); palavras soltas como "features" no texto não são tocadas.
    for a, n in sorted(mapa_texto.items(), key=lambda kv: -len(kv[0])):
        if '/' not in a:
            continue
        texto = re.sub(r'(?<![\w./-])' + re.escape(a) + r'(?![\w-])', n, texto)
        if not a.endswith('/'):
            texto = re.sub(r'(?<![\w./-])' + re.escape(a + '/'), n + '/', texto)
    if texto != original:
        total += 1
        if not SIMULAR:
            open(os.path.join(raiz, doc_novo), 'w', encoding='utf-8').write(texto)
        a_linhas, n_linhas = original.splitlines(), texto.splitlines()
        print(f'== {doc_novo}' + (f'  (antes: {doc_antigo})' if doc_antigo != doc_novo else ''))
        for x, y in zip(a_linhas, n_linhas):
            if x != y:
                print(f'   - {x.strip()[:150]}\n   + {y.strip()[:150]}')
print(f'documentos {"que seriam " if SIMULAR else ""}alterados: {total}')
