"""Importa cada módulo de src/pipeline e cada script de scripts/ (sem executar o main). Roda no container."""
import importlib
import importlib.util
import json
import subprocess
import sys
import traceback
from pathlib import Path

RAIZ = Path('/repo')
sys.path[:0] = [str(RAIZ / 'src'), str(RAIZ), str(RAIZ / 'scripts')]
resultado = {}
arquivos = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', 'src/pipeline', 'scripts'],
                                   cwd=RAIZ, text=True).split()
for f in sorted(arquivos):
    if not f.endswith('.py') or not (RAIZ / f).is_file() or f.endswith('_bootstrap.py'):
        continue
    try:
        if f.startswith('src/'):
            partes = Path(f).with_suffix('').parts[1:]
            nome = '.'.join(partes[:-1] if partes[-1] == '__init__' else partes)
            importlib.import_module(nome)
        else:
            spec = importlib.util.spec_from_file_location('_script_' + Path(f).stem, RAIZ / f)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod  # dataclasses exigem o módulo registrado
            spec.loader.exec_module(mod)  # sem __name__ == '__main__': o main não roda
        resultado[f] = 'ok'
    except BaseException as exc:  # noqa: BLE001 - queremos registrar qualquer falha de import
        resultado[f] = f'ERRO {type(exc).__name__}: {exc}'.splitlines()[0][:200]
        traceback.print_exc(limit=1)
print(json.dumps(resultado, ensure_ascii=False, indent=1, sort_keys=True))
