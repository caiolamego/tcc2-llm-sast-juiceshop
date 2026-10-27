"""Adaptador de leitura da AST TypeScript local, sem executar código do alvo."""
import hashlib
import json
from pathlib import Path
import subprocess

HELPER = Path(__file__).with_name('estrutura.cjs')


def identidade(checkout):
    modulo = Path(checkout) / 'node_modules/typescript/lib/typescript.js'
    return {'typescript_sha256': hashlib.sha256(modulo.read_bytes()).hexdigest(),
            'helper_sha256': hashlib.sha256(HELPER.read_bytes()).hexdigest()}


def analisar(path, antes, depois, checkout):
    if Path(path).suffix.lower() not in {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}:
        raise ValueError('Contexto estrutural disponível apenas para JS/TS')
    modulo = Path(checkout).resolve() / 'node_modules/typescript/lib/typescript.js'
    original = identidade(checkout)
    result = subprocess.run(['node', str(HELPER), str(modulo)],
                            input=json.dumps({'path': path, 'antes': antes.decode('utf-8'),
                                              'depois': depois.decode('utf-8')}),
                            text=True, capture_output=True, timeout=15, check=True)
    data = json.loads(result.stdout)
    if identidade(checkout) != original:
        raise ValueError('Parser alterado durante a comparação')
    if data['antes'].get('erro') or data['depois'].get('erro'):
        raise ValueError('Sintaxe não reconhecida pelo parser estrutural')
    data['identidade'] = original
    return data
