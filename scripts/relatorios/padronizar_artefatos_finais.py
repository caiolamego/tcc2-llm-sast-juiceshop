#!/usr/bin/env python3
"""Publica cópias dos artefatos com OWASP no nome, índices e métricas coerentes."""
import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e09_metricas import digest, exigir
from scripts.relatorios.atualizar_resultados_finais import CAMPANHAS
from scripts.relatorios.consolidar_metricas import main as consolidar

PREFIXO = re.compile(r'(AMP[0-9a-f]{16})_(SEMOWASP|A\d{2})_')


def nome_revisado(texto, categorias):
    def trocar(m):
        exigir(m[1] in categorias, f'Caso sem classificação: {m[1]}')
        return m[1] + '_' + categorias[m[1]] + '_'
    return PREFIXO.sub(trocar, texto)


def transformar(valor, trocar):
    if isinstance(valor, str):
        return trocar(valor)
    if isinstance(valor, list):
        return [transformar(x, trocar) for x in valor]
    if isinstance(valor, dict):
        pares = [(trocar(k), transformar(v, trocar)) for k, v in valor.items()]
        exigir(len({k for k, _ in pares}) == len(pares), 'Colisão de referências após renomeação')
        return dict(pares)
    return valor


def copiar_arvore(origem, destino, categorias, metadados):
    """Somente índices declarados podem mudar; todos os demais bytes são preservados."""
    arquivos = sorted(p for p in origem.rglob('*') if p.is_file())
    nomes = [nome_revisado(p.relative_to(origem).as_posix(), categorias) for p in arquivos]
    exigir(len(set(nomes)) == len(nomes), 'Colisão de nomes de artefatos')
    mapa = []
    for p, novo in zip(arquivos, nomes):
        exigir(not p.is_symlink(), 'Symlink de artefato não suportado')
        q = destino / novo
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
        h = digest(p)
        exigir(digest(q) == h, 'Cópia de artefato divergente')
        mapa.append({'origem': p.relative_to(RAIZ_REPO).as_posix(),
                     'destino': q.relative_to(RAIZ_REPO).as_posix(),
                     'nome_alterado': p.relative_to(origem).as_posix() != novo,
                     'indice_reescrito': p.relative_to(origem).as_posix() in metadados,
                     'sha256_original': h})
    return mapa


def escrever_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def preparar_campanha(execucao, destino, categorias):
    origem = RAIZ_REPO/'outputs/campanha_docker'/execucao
    fonte_rris = RAIZ_REPO/'outputs/rris'/execucao
    campanha, rris = destino/'campanha', destino/'rris'
    registros = 'resultados_consolidados/execucoes.jsonl'
    sessoes = f'resultados_consolidados/{execucao}_sessoes.json'
    mapa = copiar_arvore(origem, campanha, categorias, {registros, sessoes})
    mapa += copiar_arvore(fonte_rris, rris, categorias, {'manifesto.json'})
    raizes = [(str(origem), str(campanha)), (str(fonte_rris), str(rris)),
              (origem.relative_to(RAIZ_REPO).as_posix(), campanha.relative_to(RAIZ_REPO).as_posix()),
              (fonte_rris.relative_to(RAIZ_REPO).as_posix(), rris.relative_to(RAIZ_REPO).as_posix())]

    def trocar(s):
        for antes, depois in raizes:
            s = s.replace(antes, depois)
        return nome_revisado(s, categorias)

    linhas = [json.loads(x) for x in (origem/registros).read_text().splitlines() if x.strip()]
    novas, ids = [], {}
    for linha in linhas:
        nova = transformar(linha, trocar)
        cid = linha['caso_id']
        nova['tentativa_id_original'] = linha['tentativa_id']
        nova['owasp_2025_original'] = linha.get('owasp_2025')
        nova['owasp_2025'] = categorias[cid]
        ids[linha['tentativa_id']] = nova['tentativa_id']
        # A verificação usa os hashes originais: apenas os caminhos mudaram.
        for arquivo, h in nova['artefatos_sha256'].items():
            exigir(digest(campanha/arquivo) == h, 'Artefato alterado na padronização')
        for referencia in nova['artefatos'].values():
            exigir((RAIZ_REPO/referencia).is_file(), f'Referência quebrada: {referencia}')
        novas.append(nova)
    exigir(len({r['tentativa_id'] for r in novas}) == len(novas), 'IDs de tentativa duplicados')
    (campanha/registros).write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in novas))
    if (origem/sessoes).exists():
        escrever_json(campanha/sessoes, transformar(json.loads((origem/sessoes).read_text()), trocar))
    escrever_json(rris/'manifesto.json', transformar(json.loads((fonte_rris/'manifesto.json').read_text()), trocar))
    for item in mapa:
        p = RAIZ_REPO/item['destino']
        item['sha256_atual'] = digest(p)
        if not item['indice_reescrito']:
            exigir(item['sha256_atual'] == item['sha256_original'], 'Conteúdo experimental alterado')
        exigir('_SEMOWASP_' not in p.as_posix(), 'Nome de artefato ainda sem categoria')
    return campanha, rris, mapa, ids


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--saida', type=Path, required=True, help='Versão nova sob outputs/resultados_finais')
    args = ap.parse_args(argv)
    destino = args.saida.resolve()
    exigir(destino.is_relative_to((RAIZ_REPO/'outputs/resultados_finais').resolve()), 'Destino fora dos resultados finais')
    exigir(not destino.exists(), 'Destino existente; use uma versão nova')
    config = RAIZ_REPO/'config/classificacao_owasp/v1'
    with (config/'classificacao-78-casos.csv').open() as f:
        classificacao = list(csv.DictReader(f))
    categorias = {r['caso_id']: r['owasp_2025_analise'] for r in classificacao}
    exigir(len(categorias) == 78, 'Classificação incompleta')
    mapa, identidades, verificacoes, tabela = [], [], {}, []
    for modelo, (execucao, esperado) in CAMPANHAS.items():
        pasta = destino/execucao
        campanha, rris, arquivos, ids = preparar_campanha(execucao, pasta, categorias)
        mapa += arquivos
        identidades += [{'execucao': execucao, 'tentativa_id_original': a,
                         'tentativa_id': b} for a, b in ids.items()]
        print(f'{modelo}: artefatos copiados e referências atualizadas.', flush=True)
        consolidar(['--execucao', execucao, '--entrada', str(campanha),
                    '--catalogo', str(RAIZ_REPO/'outputs/catalogos/ampliado_v1/catalogo_issues.json'),
                    '--saida', str(pasta/'metricas'), '--definicao-f', 'criterio',
                    '--evidencia-rris', str(rris/'manifesto.json'), '--classificacao-owasp', str(config)])
        antes = json.loads((RAIZ_REPO/'outputs/rris'/(execucao+'_METRICAS')/'metricas.json').read_text())
        depois = json.loads((pasta/'metricas/metricas.json').read_text())
        campos = ('populacoes', 'casos', 'metricas_por_caso', 'cobertura', 'custos_tempos', 'operacional_llm')
        for campo in campos:
            exigir(antes[campo] == depois[campo], f'Resultado alterado: {campo}')
        inverso = {b: a for a, b in ids.items()}
        exigir(antes['RRIS'] == transformar(depois['RRIS'], lambda s: inverso.get(s, s)), 'Resultado RRIS alterado')
        with (pasta/'metricas/casos.csv').open() as f:
            casos = list(csv.DictReader(f))
        exigir(len(casos) == 78 and sum(c['aceito_criterio']=='true' for c in casos)==esperado, 'Totais de aceites divergentes')
        for cat in sorted(set(categorias.values())):
            grupo = [c for c in casos if c['owasp_2025'] == cat]
            tabela.append({'modelo': modelo, 'execucao': execucao, 'owasp_2025': cat,
                          'casos_aceitos': sum(c['aceito_criterio']=='true' for c in grupo),
                          'total_casos': len(grupo), 'definicao_f': 'criterio'})
        verificacoes[execucao] = {'modelo': modelo, 'tentativas': len(ids),
            'ids_ajustados': sum(a!=b for a,b in ids.items()), 'casos': 78, 'aceitos': esperado,
            'metricas_preservadas': list(campos)+['RRIS'],
            'manifesto_metricas_sha256': digest(pasta/'metricas/manifesto.json')}
    for nome, linhas in [('mapa_artefatos.csv', mapa), ('mapa_tentativas.csv', identidades), ('aceites_por_owasp.csv', tabela)]:
        with (destino/nome).open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0]), lineterminator='\n')
            w.writeheader()
            w.writerows(linhas)
    escrever_json(destino/'conferencia.json', {
        'schema_versao': '1.0', 'tipo': 'padronizacao_documental_posterior_as_campanhas',
        'classificacao_manifesto_sha256': digest(config/'manifesto.json'),
        'campanhas': verificacoes, 'arquivos': len(mapa),
        'arquivos_renomeados': sum(x['nome_alterado'] for x in mapa),
        'indices_reescritos': sum(x['indice_reescrito'] for x in mapa),
        'fontes_preservadas': True,
        'indices_sha256': {n: digest(destino/n) for n in ('mapa_artefatos.csv', 'mapa_tentativas.csv', 'aceites_por_owasp.csv')},
    })
    print(f'Concluído: {len(mapa)} arquivos e {len(identidades)} tentativas conferidos.', flush=True)


if __name__ == '__main__':
    main()
