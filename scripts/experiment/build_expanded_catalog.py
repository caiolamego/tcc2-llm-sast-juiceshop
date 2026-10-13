#!/usr/bin/env python3
"""Gera catálogo por ocorrência a partir de evidências arquivadas, sem scan ou LLM."""
from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
from pipeline.caminhos import RAIZ_REPO  # noqa: E402

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile

import yaml

BASE = RAIZ_REPO / 'outputs/auditoria_sast/combinado-hZGD7r'
DEFAULTS = {
    'scan': BASE / 'scan.json',
    'classificacao': BASE / 'triagem-final/alertas_classificados.json',
    'resumo': BASE / 'triagem-final/resumo.json',
    'manifesto_scan': BASE / 'manifesto.json',
    'mapa_cwe': RAIZ_REPO / 'config/mapa_cwe_vuln.yaml',
    'mapa_owasp': RAIZ_REPO / 'config/mapa_owasp.yaml',
    'mapa_rag': RAIZ_REPO / 'config/mapa_categoria_rag.yaml',
}
STATUS = ('confirmado', 'falso_positivo', 'inconclusivo', 'fora_escopo')
LIMITACOES = [
    'Identidade restrita às ocorrências no baseline; não compara findings após patches.',
    'O perfil remoto histórico não está congelado; os JSONs preservam a observação arquivada.',
    'Catálogo ainda não integrado automaticamente ao orquestrador atual.',
]


class CatalogoErro(ValueError):
    """Dados ou ambiente incompatíveis com o contrato do catálogo."""


def exigir(condicao, mensagem):
    if not condicao:
        raise CatalogoErro(mensagem)


def sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def serializar(dados) -> bytes:
    return (json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def texto(valor, campo, vazio=True):
    exigir(isinstance(valor, str) and (vazio or bool(valor.strip())), f'{campo}: texto inválido')
    return valor


def inteiro(valor, campo, minimo=0):
    exigir(type(valor) is int and valor >= minimo, f'{campo}: inteiro >= {minimo} esperado')
    return valor


def textos(valor, campo, aceita_string=False):
    if valor is None:
        return []
    if aceita_string and isinstance(valor, str):
        return [valor]
    exigir(isinstance(valor, list) and all(isinstance(x, str) for x in valor), f'{campo}: lista textual inválida')
    return valor


def objeto(valor, campo):
    exigir(isinstance(valor, dict), f'{campo}: objeto esperado')
    return valor


def normalizar_caminho(valor, raiz_scan: str) -> str:
    texto(valor, 'caminho', vazio=False)
    p = PurePosixPath(valor)
    exigir('..' not in p.parts and '\\' not in valor, f'Caminho inválido: {valor}')
    if p.is_absolute():
        raiz = PurePosixPath(raiz_scan)
        exigir(raiz.is_absolute() and '..' not in raiz.parts, 'Raiz original do scan deve ser absoluta e sem ..')
        try:
            p = p.relative_to(raiz)
        except ValueError as exc:
            raise CatalogoErro(f'Caminho fora da raiz original: {valor}') from exc
    exigir(bool(p.parts) and not p.is_absolute(), f'Caminho relativo inválido: {valor}')
    return p.as_posix()


@dataclass
class Fontes:
    dados: dict
    caminhos: dict[str, Path]
    hashes: dict[str, str]
    proveniencia: dict


def carregar_fontes(caminhos: dict[str, Path]) -> Fontes:
    dados, hashes, proveniencia = {}, {}, {}
    for papel, caminho in caminhos.items():
        caminho = Path(caminho).resolve()
        try:
            bruto = caminho.read_bytes()
            valor = yaml.safe_load(bruto.decode('utf-8')) if papel.startswith('mapa_') else json.loads(bruto)
        except (OSError, ValueError, UnicodeError, yaml.YAMLError) as exc:
            raise CatalogoErro(f'{papel} ({caminho}): {exc}') from exc
        dados[papel], hashes[papel] = valor, sha(bruto)
        try:
            nome = caminho.relative_to(RAIZ_REPO).as_posix()
        except ValueError:
            nome = caminho.name
        proveniencia[papel] = {'arquivo': nome, 'sha256': hashes[papel]}
        if papel.startswith('mapa_'):
            objeto(valor, papel)
            exigir(all(isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in valor.items()), f'{papel}: mapa textual inválido')
    return Fontes(dados, {k: Path(v).resolve() for k, v in caminhos.items()}, hashes, proveniencia)


def validar_associacoes(fontes: Fontes, raiz_scan: str) -> list[tuple[dict, dict]]:
    d = fontes.dados
    scan, resumo, manifesto = (objeto(d[k], k) for k in ('scan', 'resumo', 'manifesto_scan'))
    resultados, classificados = scan.get('results'), d['classificacao']
    exigir(isinstance(resultados, list) and isinstance(classificados, list), 'Scan/classificação: listas esperadas')
    exigir(isinstance(scan.get('errors', []), list), 'scan.errors: lista esperada')
    commit = texto(resumo.get('commit_alvo'), 'commit_alvo', vazio=False)
    exigir(re.fullmatch(r'[0-9a-f]{40}', commit), 'Commit deve ser SHA completo')
    versao = texto(scan.get('version'), 'scan.version', vazio=False)
    exigir(commit == manifesto.get('commit_alvo'), 'Commit divergente entre fontes')
    exigir(versao == resumo.get('semgrep_versao') == manifesto.get('semgrep_versao'), 'Versão Semgrep divergente')
    exigir(fontes.hashes['scan'] == resumo.get('scan_sha256') == manifesto.get('scan_sha256'), 'Hash do scan divergente')
    n = len(resultados)
    exigir(inteiro(resumo.get('alertas_brutos'), 'alertas_brutos') == n == inteiro(manifesto.get('findings'), 'findings') == len(classificados), 'Contagem bruta divergente')
    numeros, pares, contagens = set(), [], Counter()
    for a in classificados:
        objeto(a, 'classificação')
        numero = inteiro(a.get('numero'), 'numero', 1)
        exigir(numero <= n and numero not in numeros, f'Alerta {numero}: número ausente/repetido/fora do scan')
        numeros.add(numero)
        r = objeto(resultados[numero - 1], f'finding {numero}')
        try:
            original = texto(a.get('regra_original'), 'regra_original', False)
            regra = texto(a.get('regra'), 'regra', False)
            exigir(original == r.get('check_id'), 'Regra original divergente')
            exigir(regra == original or (regra.startswith('tcc.') and original.endswith('.' + regra)), 'Regra normalizada divergente')
            arquivo = texto(a.get('arquivo'), 'arquivo', False)
            exigir(not PurePosixPath(arquivo).is_absolute() and normalizar_caminho(arquivo, raiz_scan) == arquivo, 'Arquivo da classificação deve ser relativo e canônico')
            exigir(normalizar_caminho(r.get('path'), raiz_scan) == arquivo, 'Arquivo divergente')
            start, end = objeto(r.get('start'), 'start'), objeto(r.get('end'), 'end')
            for point in (start, end):
                inteiro(point.get('line'), 'line', 1)
                inteiro(point.get('col'), 'col', 1)
                if point.get('offset') is not None:
                    inteiro(point['offset'], 'offset')
            exigir((start['line'], start['col']) <= (end['line'], end['col']), 'Intervalo invertido')
            if start.get('offset') is not None and end.get('offset') is not None:
                exigir(start['offset'] <= end['offset'], 'Offsets invertidos')
            exigir(inteiro(a.get('inicio'), 'inicio', 1) == start['line'] and inteiro(a.get('fim'), 'fim', 1) == end['line'], 'Linhas divergentes')
            exigir(a.get('status') in STATUS, 'Status desconhecido')
            texto(a.get('motivo'), 'motivo', vazio=a['status'] != 'fora_escopo')
            for key in ('desafios', 'referencias_historicas'):
                exigir(isinstance(a.get(key), list), f'{key}: lista esperada')
                textos(a[key], key)
        except CatalogoErro as exc:
            raise CatalogoErro(f'Alerta {numero} ({a.get("arquivo")}): {exc}') from exc
        contagens[a['status']] += 1
        pares.append((a, r))
    triagem = objeto(resumo.get('triagem'), 'resumo.triagem')
    exigir(set(triagem) <= set(STATUS), 'Status desconhecido no resumo')
    for status in STATUS:
        exigir(inteiro(triagem.get(status, 0), f'triagem.{status}') == contagens[status], f'Contagem divergente: {status}')
    return pares


def git(worktree: Path, *args: str) -> str:
    try:
        return subprocess.run(['git', '-C', str(worktree), *args], check=True, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise CatalogoErro(f'Git em {worktree}: {exc}') from exc


def conferir_checkout(worktree: Path, commit: str):
    exigir(worktree.is_dir(), f'Checkout inexistente: {worktree}')
    exigir(Path(git(worktree, 'rev-parse', '--show-toplevel')).resolve() == worktree.resolve(), 'Worktree deve ser a raiz do checkout')
    exigir(git(worktree, 'rev-parse', 'HEAD') == commit, 'Commit do checkout divergente')
    exigir(not git(worktree, 'status', '--porcelain', '--untracked-files=all'), 'Checkout modificado; nenhuma alteração foi desfeita')


def ler_fonte(worktree: Path, arquivo: str) -> bytes:
    caminho = (worktree / arquivo).resolve()
    exigir(caminho.is_relative_to(worktree.resolve()) and caminho.is_file(), f'Arquivo ausente, não regular ou fora do checkout: {arquivo}')
    return caminho.read_bytes()


def contexto(worktree: Path, item: dict, arquivos: dict) -> dict:
    arquivo = item['arquivo']
    bruto = ler_fonte(worktree, arquivo)
    try:
        linhas = bruto.decode('utf-8').splitlines(keepends=True)
    except UnicodeError as exc:
        raise CatalogoErro(f'{arquivo}: UTF-8 inválido') from exc
    exigir(1 <= item['linha_inicio'] <= item['linha_fim'] <= len(linhas), f'{arquivo}: linhas fora do arquivo')
    for key in ('offset_inicio', 'offset_fim'):
        exigir(item[key] is None or item[key] <= len(bruto), f'{arquivo}: {key} fora do arquivo')
    digest = sha(bruto)
    exigir(arquivo not in arquivos or arquivos[arquivo] == digest, f'{arquivo}: modificado durante leitura')
    arquivos[arquivo] = digest
    inicio, fim = max(1, item['linha_inicio'] - 3), min(len(linhas), item['linha_fim'] + 3)
    return {'trecho': ''.join(linhas[inicio - 1:fim]), 'trecho_linha_inicio': inicio,
            'trecho_linha_fim': fim, 'linhas_arquivo': len(linhas), 'arquivo_sha256': digest,
            'modo_contexto': 'arquivo_completo' if len(linhas) <= 250 else 'janela_contexto'}


def identidade(commit: str, a: dict, r: dict) -> str:
    chave = [commit, a['regra'], a['arquivo'], r['start']['line'], r['start']['col'], r['end']['line'], r['end']['col']]
    return sha(json.dumps(chave, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def enriquecer(r: dict, fontes: Fontes) -> dict:
    extra = objeto(r.get('extra', {}), 'extra')
    meta = objeto(extra.get('metadata', {}), 'extra.metadata')
    cwe = textos(meta.get('cwe'), 'cwe', True)
    owasp = textos(meta.get('owasp'), 'owasp', True)
    ids = list(dict.fromkeys(m.group(0) for c in cwe if (m := re.match(r'CWE-\d+\b', c))))
    mapas = fontes.dados
    sigla = next((mapas['mapa_cwe'][c] for c in ids if mapas['mapa_cwe'].get(c)), 'OUTRO')
    codigo = next((m.group(1) for o in owasp if (m := re.match(r'(A\d{2}):2025\b', o))), None)
    if codigo is None:
        codigo = next((mapas['mapa_owasp'][m.group(0)] for o in owasp
                       if (m := re.match(r'A\d{2}:2021\b', o)) and mapas['mapa_owasp'].get(m.group(0))), None)
    for value, field in ((extra.get('severity'), 'severity'), (meta.get('category'), 'category')):
        if value is not None:
            texto(value, field)
    return {'severidade': extra.get('severity'), 'categoria_sast': meta.get('category'),
            'mensagem': texto(extra.get('message', ''), 'message'), 'cwe': cwe, 'cwe_ids': ids,
            'owasp_original': owasp, 'owasp_2025': codigo, 'sigla_vuln': sigla,
            'categoria_rag': mapas['mapa_rag'].get(sigla) or 'generico'}


def construir(fontes: Fontes, worktree: Path, raiz_scan: str) -> tuple[dict[str, bytes], dict]:
    pares = validar_associacoes(fontes, raiz_scan)
    commit = fontes.dados['resumo']['commit_alvo']
    conferir_checkout(worktree, commit)
    catalogo, exclusoes, arquivos, vistos, ids = [], [], {}, {}, {}
    for a, r in pares:
        assinatura = identidade(commit, a, r)
        exigir(assinatura not in vistos, f'Identidade duplicada: alertas {vistos.get(assinatura)} e {a["numero"]}')
        vistos[assinatura] = a['numero']
        item = {'assinatura_ocorrencia': assinatura, 'commit_alvo': commit,
                'check_id': a['regra'], 'check_id_original': a['regra_original'], 'arquivo': a['arquivo'],
                'linha_inicio': r['start']['line'], 'coluna_inicio': r['start']['col'],
                'linha_fim': r['end']['line'], 'coluna_fim': r['end']['col'],
                'offset_inicio': r['start'].get('offset'), 'offset_fim': r['end'].get('offset'),
                'classificacao_auditoria': a['status'],
                'origem': {'numero_alerta': a['numero'], 'indice_resultado_scan': a['numero'] - 1}}
        if a['status'] == 'fora_escopo':
            exclusoes.append({**item, 'motivo_exclusao': a['motivo']})
            continue
        case_id = 'AMP' + assinatura[:16]
        exigir(case_id not in ids, f'Colisão de ID curto: {case_id}')
        ids[case_id] = assinatura
        try:
            item.update(enriquecer(r, fontes))
            item.update(contexto(worktree, item, arquivos))
        except (CatalogoErro, OSError) as exc:
            raise CatalogoErro(f'Alerta {a["numero"]} ({a["arquivo"]}): {exc}') from exc
        item.update(caso_id=case_id, justificativa_auditoria=a['motivo'], desafios=a['desafios'],
                    referencias_historicas=a['referencias_historicas'], elegivel=True, motivo_exclusao=None)
        catalogo.append(item)
    def ordem(i):
        return tuple(i[k] for k in ('arquivo', 'linha_inicio', 'coluna_inicio', 'linha_fim', 'coluna_fim', 'check_id'))
    catalogo.sort(key=ordem)
    exclusoes.sort(key=ordem)
    artefatos = {'catalogo_issues.json': serializar(catalogo), 'exclusoes.json': serializar(exclusoes)}
    contagens = {'alertas_brutos': len(pares), 'casos_incluidos': len(catalogo), 'alertas_excluidos': len(exclusoes),
                 'por_classificacao': {s: sum(a['status'] == s for a, _ in pares) for s in STATUS},
                 'por_severidade': dict(Counter(c['severidade'] if c['severidade'] is not None else 'SEM_DADO' for c in catalogo)),
                 'incluidos_sem_cwe': sum(not c['cwe_ids'] for c in catalogo),
                 'incluidos_sem_owasp': sum(c['owasp_2025'] is None for c in catalogo),
                 'incluidos_rag_generico': sum(c['categoria_rag'] == 'generico' for c in catalogo),
                 'avisos_parsing': len(fontes.dados['scan'].get('errors', []))}
    meta = {'schema_versao': '1.0', 'catalogo_tipo': 'ampliado_por_ocorrencia', 'politica_versao': 'escopo_apenas_v1',
            'unidade': 'ocorrencia_regra_arquivo_intervalo_no_commit', 'commit_alvo': commit,
            'semgrep_versao': fontes.dados['scan']['version'], 'raiz_original_scan': PurePosixPath(raiz_scan).as_posix(),
            'fontes': fontes.proveniencia, 'contagens': contagens, 'arquivos_fonte': arquivos,
            'artefatos': {k: sha(v) for k, v in artefatos.items()}, 'limitacoes': LIMITACOES}
    artefatos['catalogo_meta.json'] = serializar(meta)
    return artefatos, meta


def revalidar(fontes: Fontes, worktree: Path, meta: dict):
    conferir_checkout(worktree, meta['commit_alvo'])
    for papel, caminho in fontes.caminhos.items():
        exigir(sha(caminho.read_bytes()) == fontes.hashes[papel], f'Fonte alterada durante geração: {papel}')
    for arquivo, digest in meta['arquivos_fonte'].items():
        exigir(sha(ler_fonte(worktree, arquivo)) == digest, f'Arquivo alterado durante geração: {arquivo}')


def publicar(saida: Path, artefatos: dict[str, bytes], verificar):
    exigir(not os.path.lexists(saida), f'Saída já existe: {saida}')
    saida.parent.mkdir(parents=True, exist_ok=True)
    lock = saida.with_name(saida.name + '.lock')
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise CatalogoErro(f'Lock existente: {lock}. Confira processos ativos antes de remover manualmente.') from exc
    temporario = None
    try:
        os.close(fd)
        exigir(not os.path.lexists(saida), f'Saída já existe: {saida}')
        temporario = Path(tempfile.mkdtemp(prefix=f'.{saida.name}-', dir=saida.parent))
        for nome, dados in artefatos.items():
            (temporario / nome).write_bytes(dados)
        verificar()
        exigir(not os.path.lexists(saida), f'Saída criada durante geração: {saida}')
        temporario.rename(saida)
        temporario = None
    finally:
        if temporario is not None:
            shutil.rmtree(temporario)
        lock.unlink()


def gerar(caminhos: dict[str, Path], worktree: Path, saida: Path, raiz_scan='/tmp/tcc-juiceshop-audit') -> dict:
    exigir(not os.path.lexists(saida), f'Saída já existe: {saida}')
    fontes = carregar_fontes(caminhos)
    artefatos, meta = construir(fontes, worktree.resolve(), raiz_scan)
    publicar(saida, artefatos, lambda: revalidar(fontes, worktree.resolve(), meta))
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worktree', required=True, type=Path)
    parser.add_argument('--saida', required=True, type=Path)
    for papel in ('scan', 'classificacao', 'resumo', 'manifesto_scan'):
        parser.add_argument('--' + papel.replace('_', '-'), type=Path, default=DEFAULTS[papel])
    parser.add_argument('--raiz-scan', default='/tmp/tcc-juiceshop-audit')
    args = parser.parse_args()
    caminhos = {**DEFAULTS, **{p: getattr(args, p) for p in ('scan', 'classificacao', 'resumo', 'manifesto_scan')}}
    try:
        meta = gerar(caminhos, args.worktree, args.saida, args.raiz_scan)
    except (CatalogoErro, OSError, ValueError) as exc:
        print(f'ERRO: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(meta['contagens'], ensure_ascii=False, sort_keys=True))
    print(f'Catálogo gravado em {args.saida}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
