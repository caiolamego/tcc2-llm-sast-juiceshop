"""Reorganiza src/pipeline (dutos e filtros, nomes em português) e scripts/ (pastas e nomes em português).

Uso: python3 reorganizar_codigo.py <raiz> [--simular]
Move os arquivos e reescreve, numa única passada por arquivo (sem trocas encadeadas):
  - nomes de módulos com ponto (imports, alvos de mock.patch, `python -m ...`);
  - imports de módulo a partir do pacote (`from pacote import modulo`), inclusive o nome local quando não há apelido;
  - caminhos em texto (src/pipeline/..., scripts/...).
Grava o mapa usado em <raiz>/.cache/reorganizacao/fase2/mapa_codigo.json.
"""
import ast
import json
import re
import sys
from pathlib import Path

RAIZ = Path(sys.argv[1]).resolve()
SIMULAR = '--simular' in sys.argv[2:]
E = 'src/pipeline/etapas'
ARQUIVOS = {
    # comum
    'src/pipeline/caminhos.py': 'src/pipeline/comum/caminhos.py',
    'src/pipeline/validation/identity.py': 'src/pipeline/comum/identidade.py',
    'src/pipeline/validation/components.py': 'src/pipeline/comum/componentes.py',
    # etapa 1: análise SAST (inicial e reanálise)
    'src/pipeline/sast/semgrep_client.py': f'{E}/e01_analise_sast/semgrep.py',
    'src/pipeline/sast/perfil.py': f'{E}/e01_analise_sast/perfil.py',
    'src/pipeline/sast/comparacao_v2.py': f'{E}/e01_analise_sast/comparacao.py',
    'src/pipeline/sast/estrutura.py': f'{E}/e01_analise_sast/estrutura.py',
    'src/pipeline/sast/estrutura.cjs': f'{E}/e01_analise_sast/estrutura.cjs',
    # etapa 2: catálogo
    'src/pipeline/catalogo.py': f'{E}/e02_catalogo/catalogo.py',
    'src/pipeline/sast/associacoes.py': f'{E}/e02_catalogo/associacoes.py',
    # etapa 3: contexto RAG
    'src/pipeline/rag/__init__.py': f'{E}/e03_contexto_rag/__init__.py',
    'src/pipeline/rag/retriever.py': f'{E}/e03_contexto_rag/recuperacao.py',
    # etapa 4: prompt
    'src/pipeline/prompts/builder.py': f'{E}/e04_prompt/montagem.py',
    # etapa 5: geração pela LLM
    'src/pipeline/llm/provider.py': f'{E}/e05_geracao_llm/provedor.py',
    'src/pipeline/llm/openai_client.py': f'{E}/e05_geracao_llm/cliente_openai.py',
    'src/pipeline/llm/colab_client.py': f'{E}/e05_geracao_llm/cliente_colab.py',
    'src/pipeline/llm/colab_protocol.py': f'{E}/e05_geracao_llm/protocolo_colab.py',
    'src/pipeline/llm/falso.py': f'{E}/e05_geracao_llm/resposta_simulada.py',
    'src/pipeline/llm/schema.py': f'{E}/e05_geracao_llm/esquema.py',
    # etapa 6: aplicação em cópia isolada
    'src/pipeline/patching/applier.py': f'{E}/e06_aplicacao/aplicador.py',
    'src/pipeline/patching/indentacao.py': f'{E}/e06_aplicacao/indentacao.py',
    'src/pipeline/target/workspace.py': f'{E}/e06_aplicacao/worktrees.py',
    # etapa 7: validação (R, F, M)
    'src/pipeline/validation/engine.py': f'{E}/e07_validacao/medicao.py',
    'src/pipeline/validation/policy.py': f'{E}/e07_validacao/politicas.py',
    'src/pipeline/validation/coverage.py': f'{E}/e07_validacao/cobertura.py',
    'src/pipeline/validation/coverage_runner.py': f'{E}/e07_validacao/execucao_cobertura.py',
    'src/pipeline/validation/coverage_audit.py': f'{E}/e07_validacao/auditoria_cobertura.py',
    'src/pipeline/validation/coverage_api_setup.mjs': f'{E}/e07_validacao/preparo_api_cobertura.mjs',
    'src/pipeline/validation/selection.py': f'{E}/e07_validacao/selecao.py',
    'src/pipeline/validation/runner.py': f'{E}/e07_validacao/camadas.py',
    'src/pipeline/validation/conjunto_d.py': f'{E}/e07_validacao/conjunto_d.py',
    'src/pipeline/validation/preparacao_api.py': f'{E}/e07_validacao/preparacao_api.py',
    'src/pipeline/validation/cache.py': f'{E}/e07_validacao/cache.py',
    'src/pipeline/validation/retry.py': f'{E}/e07_validacao/repeticao.py',
    # etapa 8: registro
    'src/pipeline/registro.py': f'{E}/e08_registro/registro.py',
    # etapa 9: métricas
    'src/pipeline/metrics/__init__.py': f'{E}/e09_metricas/__init__.py',
    'src/pipeline/metrics/loader.py': f'{E}/e09_metricas/leitura.py',
    'src/pipeline/metrics/normalizer.py': f'{E}/e09_metricas/normalizacao.py',
    'src/pipeline/metrics/calculator.py': f'{E}/e09_metricas/calculo.py',
    'src/pipeline/metrics/exporter.py': f'{E}/e09_metricas/publicacao.py',
    'src/pipeline/metrics/rris.py': f'{E}/e09_metricas/rris.py',
    # orquestração e interfaces
    'src/pipeline/run_pipeline.py': 'src/pipeline/orquestracao/campanha.py',
    'src/pipeline/execucao_ampliada.py': 'src/pipeline/orquestracao/preflight.py',
    'src/pipeline/painel/controller.py': 'src/pipeline/painel/controle.py',
    'src/pipeline/painel/server.py': 'src/pipeline/painel/servidor.py',
    # legado (modo histórico E01-E03)
    'src/pipeline/sast/filtro.py': 'src/pipeline/legado/filtro.py',
    'src/pipeline/sast/comparacao.py': 'src/pipeline/legado/comparacao_v1.py',
}
SCRIPTS = {
    'setup': ('preparacao', {'setup_target.sh': 'preparar_alvo.sh',
                             'prepare_api_worktrees.py': 'preparar_worktrees_api.py'}),
    'experiment': ('experimento', {
        'build_expanded_catalog.py': 'gerar_catalogo_ampliado.py',
        'build_issue_catalog.py': 'gerar_catalogo_historico.py',
        'validate_functional_coverage.py': 'gerar_baseline_funcional.py',
        'baseline_testes.py': 'gerar_linha_de_base_historica.py',
        'benchmark_validation.py': 'replay_patches.py',
        'replay_anchor_application.py': 'replay_ancoras.py',
        'diagnose_llm.py': 'diagnosticar_llm.py',
        'validate_knowledge_base.py': 'validar_base_rag.py',
        'mark_juiceshop_challenges.py': 'marcar_desafios_historicos.py',
        'measure_validation_cost.py': 'medir_custo_validacao.py',
        'try_one.py': 'tentar_um_caso.py',
        'validate_runner_scenarios.py': 'validar_cenarios_camadas.py'}),
    'reports': ('relatorios', {
        'consolidate_metrics.py': 'consolidar_metricas.py',
        'metricas_execucao.py': 'metricas_historicas.py',
        'report_baseline.py': 'relatorio_baseline_historico.py',
        'report_patch_revalidation.py': 'relatorio_revalidacao.py',
        'report_validation_benchmark.py': 'relatorio_replays.py',
        **{f'report_rodada{n}.py': f'relatorio_rodada{n}.py' for n in range(2, 13)}}),
    'audit': ('auditoria', {
        'audit_functional_coverage.py': 'auditar_cobertura_funcional.py',
        'audit_semgrep_coverage.py': 'auditar_cobertura_semgrep.py',
        'build_challenge_matrix.py': 'gerar_matriz_desafios.py',
        'build_repair_candidates.py': 'gerar_candidatos_correcao.py',
        'build_sast_profile.py': 'congelar_perfil_sast.py',
        'classify_combined_scan.py': 'classificar_scan_combinado.py',
        'compare_functional_baselines.py': 'comparar_baselines_funcionais.py',
        'evaluate_reference_fixes.py': 'avaliar_codefixes.py',
        'recompare_archived_scans.py': 'recomparar_scans_arquivados.py',
        'review_associations.py': 'revisar_associacoes.py',
        'test_rodada.py': 'testar_rodada.py',
        **{f'verify_rodada{n}.py': f'verificar_rodada{n}.py' for n in range(8, 13)}}),
}
for antiga, (nova, nomes) in SCRIPTS.items():
    for f in sorted((RAIZ / 'scripts' / antiga).iterdir()):
        if f.is_file():
            ARQUIVOS[f'scripts/{antiga}/{f.name}'] = f'scripts/{nova}/{nomes.get(f.name, f.name)}'


def modulo(caminho):
    p = Path(caminho)
    if p.suffix != '.py':
        return None
    partes = p.with_suffix('').parts
    partes = partes[1:] if partes[0] == 'src' else partes
    return '.'.join(partes[:-1] if partes[-1] == '__init__' else partes)


MODULOS = {modulo(a): modulo(n) for a, n in ARQUIVOS.items() if modulo(a)}
# Pacotes que deixam de existir com o nome antigo (usados em "from pacote import nome").
MODULOS.update({'scripts.' + a: 'scripts.' + n for a, (n, _) in SCRIPTS.items()})
PACOTES_SEM_INIT = {'pipeline.sast', 'pipeline.validation', 'pipeline.llm', 'pipeline.patching',
                    'pipeline.prompts', 'pipeline.target'}
# Mapa de pastas (para links e menções a diretórios).
PASTAS = {'src/pipeline/' + p: None for p in ('sast', 'validation', 'llm', 'patching', 'prompts', 'target', 'rag', 'metrics')}
PASTAS.update({f'scripts/{a}': f'scripts/{n}' for a, (n, _) in SCRIPTS.items()})

re_mod = re.compile(r'(?<![A-Za-z0-9_.])(' + '|'.join(re.escape(k) for k in sorted(MODULOS, key=len, reverse=True)) + r')(?![A-Za-z0-9_])')
re_arq = re.compile(r'(?<![A-Za-z0-9_.-])(' + '|'.join(re.escape(k) for k in sorted(ARQUIVOS, key=len, reverse=True)) + r')(?![A-Za-z0-9_-])')
re_pasta = re.compile(r'(?<![A-Za-z0-9_.-])(scripts/(?:setup|experiment|reports|audit))(?=/|`|\s|$|\)|\'|")')


def reescrever_imports_modulo(texto, arquivo):
    """from pacote import modulo [as apelido] -> novo pacote/nome; sem apelido, troca também o nome local."""
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return texto
    renomear_local = {}
    linhas = texto.split('\n')
    for n in ast.walk(arvore):
        if not (isinstance(n, ast.ImportFrom) and n.module and n.module.split('.')[0] in ('pipeline', 'scripts')):
            continue
        partes_novas = []
        mudou = False
        for a in n.names:
            completo = f'{n.module}.{a.name}'
            if completo in MODULOS and completo not in ('scripts.' + k for k in SCRIPTS):
                novo_pai, novo_nome = MODULOS[completo].rsplit('.', 1)
                partes_novas.append((novo_pai, novo_nome, a.asname))
                if a.asname is None and novo_nome != a.name:
                    renomear_local[a.name] = novo_nome
                mudou = True
            else:
                partes_novas.append((None, a.name, a.asname))
        if not mudou:
            continue
        pais = {p for p, _, _ in partes_novas if p}
        if len(pais) != 1 or any(p is None for p, _, _ in partes_novas) or n.lineno != n.end_lineno:
            raise SystemExit(f'Import complexo, revisar à mão: {arquivo}:{n.lineno}')
        ind = re.match(r'\s*', linhas[n.lineno - 1]).group(0)
        nomes = ', '.join(nome + (f' as {apl}' if apl else '') for _, nome, apl in partes_novas)
        linhas[n.lineno - 1] = f'{ind}from {pais.pop()} import {nomes}' + (
            '  # noqa: E402' if 'noqa: E402' in linhas[n.lineno - 1] else '')
    texto = '\n'.join(linhas)
    for antigo, novo in renomear_local.items():
        texto = re.sub(r'(?<![A-Za-z0-9_.])' + re.escape(antigo) + r'\.(?=[A-Za-z_])', novo + '.', texto)
        texto = re.sub(r'(?<![A-Za-z0-9_.])' + re.escape(antigo) + r'(?=\.__file__)', novo, texto)
    return texto


def reescrever(texto, arquivo):
    if arquivo.endswith('.py'):
        texto = reescrever_imports_modulo(texto, arquivo)
    texto = re_mod.sub(lambda m: MODULOS[m.group(1)], texto)
    texto = re_arq.sub(lambda m: ARQUIVOS[m.group(1)], texto)
    texto = re_pasta.sub(lambda m: PASTAS[m.group(1)], texto)
    return texto


def alvos_de_texto():
    """Arquivos de código, testes e configuração reescritos (documentação é tratada à parte)."""
    import subprocess
    todos = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard'], cwd=RAIZ, text=True).split()
    sufixos = ('.py', '.mjs', '.cjs', '.sh', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.txt')
    nomes = ('Makefile', 'Dockerfile', 'compose.yaml', '.env.example', '.dockerignore')
    for f in todos:
        if f.startswith(('outputs/', 'docs/', 'workspace/', '.cache/', 'knowledge_base/', 'rules/')):
            continue
        if f == 'docker/referencia.json' or f.startswith('tests/integration/historico/'):
            continue
        if f.endswith(sufixos) or Path(f).name in nomes or (f.startswith('tests/') and f.endswith('.md')):
            yield f


# 1) mover
for a, n in ARQUIVOS.items():
    if not (RAIZ / a).is_file():
        raise SystemExit(f'origem ausente: {a}')
    if (RAIZ / n).exists() and a != n:
        raise SystemExit(f'destino já existe: {n}')
alvos = [f for f in alvos_de_texto() if (RAIZ / f).is_file()]
novos_caminhos = {f: ARQUIVOS.get(f, f) for f in alvos}
if not SIMULAR:
    for a, n in ARQUIVOS.items():
        (RAIZ / n).parent.mkdir(parents=True, exist_ok=True)
        (RAIZ / a).rename(RAIZ / n)
    for pasta in ('sast', 'validation', 'llm', 'patching', 'prompts', 'target', 'rag', 'metrics'):
        p = RAIZ / 'src/pipeline' / pasta
        for lixo in p.glob('__pycache__'):
            import shutil
            shutil.rmtree(lixo)
        if p.exists():
            p.rmdir()
    for antiga in SCRIPTS:
        p = RAIZ / 'scripts' / antiga
        for lixo in p.glob('__pycache__'):
            import shutil
            shutil.rmtree(lixo)
        p.rmdir()

# 2) reescrever
alterados = 0
for antigo, novo in sorted(novos_caminhos.items()):
    caminho = RAIZ / (novo if not SIMULAR else antigo)
    texto = caminho.read_text(encoding='utf-8')
    saida = reescrever(texto, novo)
    if saida != texto:
        alterados += 1
        print(f'reescrito: {novo}' + (f'  (antes: {antigo})' if antigo != novo else ''))
        if not SIMULAR:
            caminho.write_text(saida, encoding='utf-8')
mapa = {'arquivos': ARQUIVOS, 'modulos': MODULOS, 'pastas': {k: v for k, v in PASTAS.items() if v}}
destino = RAIZ / '.cache/reorganizacao/fase2/mapa_codigo.json'
destino.write_text(json.dumps(mapa, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
print(f'{len(ARQUIVOS)} arquivos {"seriam movidos" if SIMULAR else "movidos"}; {alterados} reescritos; mapa em {destino}')
