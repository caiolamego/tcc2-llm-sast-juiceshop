#!/usr/bin/env python3
"""Publica nova consolidação das três campanhas com a classificação OWASP revisada."""
import argparse
import csv
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e09_metricas import digest, exigir
from scripts.relatorios.consolidar_metricas import main as consolidar

CAMPANHAS = {
    'GPT-4.1 mini': ('AMP_REAL_20261106T151004Z_f49ac0d2', 38),
    'GPT-5.6 Luna': ('AMP_REAL_20261106T125801Z_0eb68fe4', 51),
    'GPT-6 Luna': ('AMP_REAL_20261106T105533Z_aa697342', 49),
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--saida', required=True, type=Path, help='Diretório novo para os resultados finais')
    args = ap.parse_args(argv)
    destino = args.saida.resolve()
    exigir(not destino.exists(), 'Use um diretório novo; resultados publicados são preservados')
    config = RAIZ_REPO/'config/classificacao_owasp/v1'
    checks, tabela = {}, []
    for modelo, (execucao, esperado) in CAMPANHAS.items():
        original = RAIZ_REPO/'outputs/rris'/(execucao + '_METRICAS')
        saida = destino/execucao
        consolidar([
            '--execucao', execucao,
            '--entrada', str(RAIZ_REPO/'outputs/campanha_docker'/execucao),
            '--catalogo', str(RAIZ_REPO/'outputs/catalogos/ampliado_v1/catalogo_issues.json'),
            '--saida', str(saida), '--definicao-f', 'criterio',
            '--evidencia-rris', str(RAIZ_REPO/'outputs/rris'/execucao/'manifesto.json'),
            '--classificacao-owasp', str(config),
        ])
        antes = json.loads((original/'metricas.json').read_text())
        depois = json.loads((saida/'metricas.json').read_text())
        campos = ('populacoes', 'metricas_por_caso', 'casos', 'cobertura',
                  'custos_tempos', 'RRIS', 'operacional_llm')
        for campo in campos:
            exigir(antes[campo] == depois[campo], f'{modelo}: resultado alterado em {campo}')
        iguais = []
        for arq in sorted(original.glob('*.csv')):
            if arq.name in ('tentativas.csv', 'casos.csv', 'metricas_por_owasp.csv'):
                continue
            exigir(arq.read_bytes() == (saida/arq.name).read_bytes(), f'CSV alterado: {arq.name}')
            iguais.append(arq.name)
        exigir((original/'metricas_por_owasp.csv').read_bytes() ==
               (saida/'metricas_por_owasp_original.csv').read_bytes(),
               f'{modelo}: agrupamento OWASP original não preservado')
        with (saida/'casos.csv').open(newline='') as f:
            casos = list(csv.DictReader(f))
        exigir(len(casos) == 78 and sum(c['aceito_criterio'] == 'true' for c in casos) == esperado,
               f'{modelo}: quantidade de casos ou aceites divergente')
        for cat in sorted({c['owasp_2025'] for c in casos}):
            grupo = [c for c in casos if c['owasp_2025'] == cat]
            exigir(bool(cat), 'Caso sem classificação OWASP')
            tabela.append({'modelo': modelo, 'execucao': execucao, 'owasp_2025': cat,
                          'casos_aceitos': sum(c['aceito_criterio'] == 'true' for c in grupo),
                          'total_casos': len(grupo), 'definicao_f': 'criterio'})
        checks[execucao] = {'modelo': modelo, 'casos': 78, 'aceitos': esperado,
                           'campos_inalterados': list(campos), 'csvs_identicos': iguais,
                           'owasp_original_identico': True,
                           'manifesto_original_sha256': digest(original/'manifesto.json'),
                           'manifesto_atual_sha256': digest(saida/'manifesto.json')}
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=list(tabela[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(tabela)
    (destino/'aceites_por_owasp.csv').write_text(buf.getvalue())
    report = {'schema_versao': '1.0', 'tipo': 'consolidacao_offline_posterior_as_campanhas',
              'classificacao_manifesto_sha256': digest(config/'manifesto.json'),
              'campanhas': checks, 'aceites_por_owasp_sha256': digest(destino/'aceites_por_owasp.csv')}
    (destino/'conferencia.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print('Conferência concluída: três campanhas, 78 casos cada; aceites 38, 51 e 49 preservados.')


if __name__ == '__main__':
    main()
