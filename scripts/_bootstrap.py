"""Inicializa imports para comandos executados diretamente ou como módulos."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
for directory in (ROOT, ROOT / "src"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
