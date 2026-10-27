"""Conjunto único de fontes relevantes para cache, contrato e integridade."""
from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.comum.identidade import digest


def componentes():
    fontes = []
    # Os mesmos 30 arquivos de antes da reorganização: SAST, aplicação, validação, legado e orquestração.
    for pasta in ('etapas/e01_analise_sast','etapas/e06_aplicacao','etapas/e07_validacao','legado'):
        fontes.extend((RAIZ_REPO/'src/pipeline'/pasta).glob('*.py'))
    fontes.extend((RAIZ_REPO/'src/pipeline/etapas/e01_analise_sast').glob('*.cjs'))
    fontes.extend((RAIZ_REPO/'src/pipeline/etapas/e07_validacao').glob('*.mjs'))
    fontes.extend(RAIZ_REPO/p for p in (
        'src/pipeline/comum/identidade.py','src/pipeline/comum/componentes.py',
        'src/pipeline/etapas/e02_catalogo/associacoes.py',
        'src/pipeline/orquestracao/campanha.py','src/pipeline/orquestracao/preflight.py',
        'src/pipeline/etapas/e02_catalogo/catalogo.py','src/pipeline/etapas/e08_registro/registro.py','config/conjunto_d.json'))
    return {p.relative_to(RAIZ_REPO).as_posix():digest(p) for p in sorted(set(fontes))}
