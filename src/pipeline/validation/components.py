"""Conjunto único de fontes relevantes para cache, contrato e integridade."""
from pipeline.caminhos import RAIZ_REPO
from pipeline.validation.identity import digest


def componentes():
    fontes = []
    for pasta in ('validation','sast','target','patching'):
        fontes.extend((RAIZ_REPO/'src/pipeline'/pasta).glob('*.py'))
    fontes.extend(RAIZ_REPO/p for p in (
        'src/pipeline/run_pipeline.py','src/pipeline/execucao_ampliada.py',
        'src/pipeline/catalogo.py','src/pipeline/registro.py','config/conjunto_d.json'))
    return {p.relative_to(RAIZ_REPO).as_posix():digest(p) for p in sorted(set(fontes))}
