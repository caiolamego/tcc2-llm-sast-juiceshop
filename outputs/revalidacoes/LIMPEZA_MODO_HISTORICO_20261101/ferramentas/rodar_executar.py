"""Roda o mesmo comando que executar.py monta, mas com ID de execução fixo (comparável antes/depois)."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, '/repo')
import executar  # noqa: E402

cfg, modo, execucao = sys.argv[1], sys.argv[2], sys.argv[3]
config = executar.carregar_config(Path(cfg))
config['modo'] = modo
pipeline, metricas = executar.montar_comandos(config, sys.executable, execucao)
r = subprocess.run(pipeline, cwd='/repo')
if r.returncode:
    sys.exit(r.returncode)
sys.exit(subprocess.run(metricas, cwd='/repo').returncode)
