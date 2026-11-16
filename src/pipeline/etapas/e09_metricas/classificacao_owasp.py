"""Classificação complementar aplicada somente às cópias da consolidação."""
import csv
from pathlib import Path
import re

from pipeline.etapas.e09_metricas import exigir, digest, ler_json, relativo


def aplicar(entrada, pasta):
    exigir(not getattr(entrada, 'classificacao_owasp', None), 'Classificação OWASP já aplicada')
    pasta = Path(pasta).resolve()
    manifesto_path = pasta / 'manifesto.json'
    manifesto = ler_json(manifesto_path)
    exigir(manifesto.get('schema_versao') == '1.0', 'Versão da classificação OWASP inválida')
    exigir(digest(entrada.catalogo.caminho) == manifesto.get('catalogo_sha256'),
           'Classificação OWASP pertence a outro catálogo')
    arquivos = manifesto.get('arquivos_sha256')
    exigir(isinstance(arquivos, dict) and 'classificacao-78-casos.csv' in arquivos,
           'Manifesto OWASP sem tabela de classificação')
    entrada.registrar(manifesto_path, 'classificacao_owasp/manifesto')
    for nome, esperado in arquivos.items():
        caminho = relativo(pasta, nome)
        exigir(digest(caminho) == esperado, f'Classificação OWASP alterada: {nome}')
        entrada.registrar(caminho, 'classificacao_owasp/' + nome)
    with (pasta / 'classificacao-78-casos.csv').open(encoding='utf-8', newline='') as arq:
        linhas = list(csv.DictReader(arq))
    por_id = {r['caso_id']: r for r in linhas}
    casos = {c['caso_id']: c for c in entrada.catalogo.casos}
    exigir(len(linhas) == len(por_id) == len(casos) == manifesto.get('casos')
           and set(por_id) == set(casos), 'População da classificação OWASP divergente ou duplicada')
    metodos = {'categoria original preservada', 'correspondência explícita CWE–OWASP',
               'associação contextual documentada'}
    for cid, r in por_id.items():
        c = casos[cid]
        exigir(r['owasp_2025_original'] == (c.get('owasp_2025') or ''),
               f'Categoria OWASP original divergente: {cid}')
        exigir(r['classificacao_auditoria'] == c['classificacao_auditoria'],
               f'Triagem divergente na classificação OWASP: {cid}')
        exigir(re.fullmatch(r'A(?:0[1-9]|10)', r['owasp_2025_analise']) is not None,
               f'Categoria OWASP inválida: {cid}')
        exigir(r['metodo'] in metodos and bool(r['justificativa'].strip()),
               f'Método ou justificativa OWASP ausente: {cid}')
        if c.get('owasp_2025'):
            exigir(r['owasp_2025_analise'] == c['owasp_2025']
                   and r['metodo'] == 'categoria original preservada',
                   f'Reclassificação de categoria original não autorizada: {cid}')
    # A validação termina antes de alterar qualquer linha normalizada.
    for row in entrada.linhas:
        r = por_id[row['caso_id']]
        row['owasp_2025_original'] = row.get('owasp_2025')
        row['owasp_2025'] = r['owasp_2025_analise']
        row['owasp_classificacao_metodo'] = r['metodo']
    entrada.classificacao_owasp = {
        'posterior_as_campanhas': True, 'manifesto_sha256': digest(manifesto_path),
        'limite': manifesto['limite'], 'casos': len(casos),
        'originais_preservados': sum(bool(c.get('owasp_2025')) for c in casos.values()),
        'metodo_por_caso': {cid: r['metodo'] for cid, r in sorted(por_id.items())},
        'categorias_por_caso': {cid: {
            'owasp_2025': r['owasp_2025_analise'],
            'owasp_2025_original': r['owasp_2025_original'] or None,
            'owasp_classificacao_metodo': r['metodo'],
        } for cid, r in sorted(por_id.items())},
    }
