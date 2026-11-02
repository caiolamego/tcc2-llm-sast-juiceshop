"""Lista links relativos quebrados em arquivos Markdown (fora de outputs/, workspace/, .cache/)."""
import re
import subprocess
import sys
from pathlib import Path

raiz = Path(sys.argv[1])
arquivos = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '*.md'], cwd=raiz, text=True).split()
padrao = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
quebrados = []
externos = []
total = 0
for nome in sorted(arquivos):
    if nome.startswith(('outputs/', 'workspace/', '.cache/')):
        continue
    caminho = raiz / nome
    if not caminho.is_file():
        continue
    for alvo in padrao.findall(caminho.read_text(encoding='utf-8', errors='replace')):
        if alvo.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        total += 1
        destino = (caminho.parent / alvo.split('#')[0]).resolve()
        if not destino.is_relative_to(raiz.resolve()):
            externos.append(f'{nome} -> {alvo}')
        elif not destino.exists():
            quebrados.append(f'{nome} -> {alvo}')
print(f'links relativos verificados: {total}; quebrados: {len(quebrados)}')
for q in quebrados:
    print('  ' + q)
print(f'links para fora do repositório (não verificáveis aqui): {len(externos)}')
for q in externos:
    print('  externo: ' + q)
