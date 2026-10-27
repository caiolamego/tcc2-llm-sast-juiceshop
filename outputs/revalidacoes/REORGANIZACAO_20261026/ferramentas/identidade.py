"""Fotografa as identidades científicas que a reorganização não pode alterar (roda no container)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, '/repo/src')
sys.path.insert(0, '/repo/docker')
from pipeline.caminhos import RAIZ_REPO  # noqa: E402
from pipeline.catalogo import carregar as carregar_catalogo  # noqa: E402
from pipeline.prompts import builder  # noqa: E402
from pipeline.rag.retriever import carregar_base  # noqa: E402
from pipeline.sast import perfil  # noqa: E402
from pipeline.validation import coverage  # noqa: E402
from pipeline.validation.components import componentes  # noqa: E402
from pipeline.validation.identity import digest  # noqa: E402
import referencia  # noqa: E402

def carregar_perfil(p):
    """carregar() valida regras, escopo e IDs; o erro, se houver, também faz parte da foto."""
    try:
        perfil.carregar(RAIZ_REPO / p)
        return {'sha256': digest(RAIZ_REPO / p), 'carrega': True}
    except ValueError as exc:
        return {'sha256': digest(RAIZ_REPO / p), 'carrega': False, 'erro': str(exc)}


rev = RAIZ_REPO / 'config/cobertura_funcional_v1.yaml'
mapa = RAIZ_REPO / 'config/mapa_testes_relacionados_v2.yaml'
cat = carregar_catalogo(RAIZ_REPO / 'outputs/catalogos/ampliado_v1/catalogo_issues.json')
dados = {
    'raiz_repo': str(RAIZ_REPO),
    'componentes': componentes(),
    'cobertura_identidade': coverage.identidade(coverage.ler_yaml(rev), rev, mapa),
    'componentes_prompt': builder.componentes_contrato(['P1', 'P2', 'P3', 'P4']),
    'roteiro_sha256': digest(builder.ARQ_ROTEIRO),
    'base_rag_sha256': carregar_base(builder.DIR_KB).hash_base,
    'perfis': {p: carregar_perfil(p)
               for p in ('config/perfis/ampliado_v1/perfil.json', 'config/perfis/ampliado_piloto_v1/perfil.json')},
    'catalogo': {'commit': cat.commit, 'casos': len(cat.casos), 'ampliado': cat.ampliado},
    'referencia_docker_entradas': {p: digest(RAIZ_REPO / p) for p in referencia.INPUTS},
    'referencia_docker_json_sha256': digest(RAIZ_REPO / 'docker/referencia.json'),
    'baseline_oficial_sha256': digest(RAIZ_REPO / 'outputs/baselines/docker/oficial_v1/BASELINE/baseline_testes.json'),
}
print(json.dumps(dados, ensure_ascii=False, sort_keys=True, indent=2))
