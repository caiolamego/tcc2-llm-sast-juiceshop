#!/usr/bin/env python3
"""Acrescenta o critério (d) ao conjunto D, por caso, sem LLM e sem sobrescrever.

Gera a nova versão do conjunto D, a revisão de cobertura que aponta para ela e o
mapa derivado. Recusa teste inexistente, caso fora do catálogo e destino existente.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
import argparse
import hashlib
import json
import re
from pipeline.comum.caminhos import RAIZ_REPO

ORIGEM='config/conjunto_d_cobertura_v1.json'
DESTINO='config/conjunto_d_cobertura_v2.json'
REVISAO='config/cobertura_funcional_v6.yaml'
REVISAO_NOVA='config/cobertura_funcional_v7.yaml'
MAPA='config/mapa_testes_relacionados_v7.yaml'
MAPA_NOVO='config/mapa_testes_relacionados_v8.yaml'
CATALOGO='outputs/catalogos/ampliado_v1/catalogo_issues.json'
CRITERIOS='docs/criterios_conjunto_d.md'

SEARCH='frontend/src/app/search-result/search-result.component.spec.ts'
FEEDBACK='test/api/feedback.test.ts'
USER='test/api/user.test.ts'
METRICS='test/api/metrics.test.ts'
INSECURITY='test/server/insecurity.unit.test.ts'
BYPASS='Exige a chamada de bypassSecurityTrust, que é o sink apontado pelo alerta.'
PUBLICA='Requisição sem credencial: exige que /metrics continue público.'
RESPOSTA='Usa o answer devolvido pelo servidor para preparar o teste: exige o vazamento.'
CADASTRO='Cadastra sem passwordRepeat: exige que a validação continue opcional.'
PAPEL='Exige que o cliente escolha o próprio papel no cadastro.'

# (arquivo, nome, casos, justificativa). Testes em tests/functional ficam no repositório.
ENTRADAS=[
 ('frontend/src/app/about/about.component.spec.ts','should add an image to the gallery for each feedback with formatted comment and stars',['AMP746c0b4d1a2f8ed4'],BYPASS),
 ('frontend/src/app/last-login-ip/last-login-ip.component.spec.ts','should set Last-Login IP from JWT as trusted HTML',['AMP417d1da8d7caa6bd'],BYPASS),
 (SEARCH,'should render product descriptions as trusted HTML',['AMPad5710627036ab1a','AMP5bc31b97699a0901'],BYPASS),
 (SEARCH,'should pass the search query as trusted HTML',['AMPad5710627036ab1a','AMP5bc31b97699a0901'],BYPASS),
 ('frontend/src/app/track-result/track-result.component.spec.ts','should consider order number as trusted HTML',['AMP5ea3343a04b7e82b'],BYPASS),
 ('test/api/ftp-folder.test.ts','GET serves a directory listing',['AMPee9d50eba0ea870a'],'Exige a página de listagem de /ftp, que é o alerta.'),
 ('test/api/file-serving.test.ts','GET serves a directory listing',['AMP5b6593d097204fd4'],'Exige a página de listagem de /encryptionkeys, que é o alerta.'),
 ('test/api/password.test.ts','GET password change for Bender without current password using GET request',['AMP9ea0dd6316734fd8'],'Exige trocar a senha sem informar a atual.'),
 ('test/api/b2b-order.test.ts','POST busy spinning regex attack does not raise an error',['AMP317527c78d15fb94'],'O 503 só existe se o código enviado pelo cliente for executado.'),
 ('test/api/b2b-order.test.ts','POST endless loop exploit in "orderLinesData" will raise explicit error',['AMP317527c78d15fb94'],'A mensagem vem do avaliador executando o código enviado pelo cliente.'),
 (INSECURITY,'returns SHA-256 HMAC with "pa4qacea4VK9t9nGv7yZtwmj" as salt any input string',['AMPf9cfcac6567b2213','AMP60988b73f0db52a7'],'Fixa o digest da chave escrita no código.'),
 (INSECURITY,'returns MD5 hash for any input string',['AMP41302bd0fb784039'],'Fixa o digest MD5 que o alerta manda substituir.'),
 ('test/api/basket.test.ts','GET existing basket with contained products by id',['AMP966898b58995c2e3'],'jim (usuário 2) lê o carrinho 1, do admin, e espera sucesso.'),
 ('test/api/basket.test.ts','POST placing an order for an existing basket returns orderId',['AMPbd16f473e192b7d4'],'jim (usuário 2) fecha o carrinho 1, do admin, e espera sucesso.'),
 ('test/api/erasure-request.test.ts','POST erasure request with non-existing file path as layout parameter throws error',['AMP70923219351e683a'],'Exige que o layout do cliente chegue ao sistema de arquivos.'),
 ('tests/functional/juice_shop/captcha_arithmetic.test.ts','calculates and persists ${expression} = ${expected}',['AMP4d38adc404310ebe'],'Afirma o answer na resposta, que é o alerta.'),
 (FEEDBACK,'POST sanitizes unsafe HTML from comment',['AMP4d38adc404310ebe'],RESPOSTA),
 (FEEDBACK,'POST feedback in a non-existing users name as anonymous user fails with constraint error',['AMP4d38adc404310ebe'],RESPOSTA),
 (FEEDBACK,'POST feedback can be created without actually supplying comment',['AMP4d38adc404310ebe'],RESPOSTA),
 (FEEDBACK,'POST feedback cannot be created without actually supplying rating',['AMP4d38adc404310ebe'],RESPOSTA),
 (FEEDBACK,'POST feedback cannot be created with wrong CAPTCHA answer',['AMP4d38adc404310ebe'],RESPOSTA),
 (FEEDBACK,'DELETE existing feedback',['AMP4d38adc404310ebe'],RESPOSTA),
 *[(METRICS,n,['AMP8be00f4f6862bdba','AMP488a4d26d36eaa6f'],PUBLICA) for n in (
   'GET with an ignored scraper user agent does not solve exposedMetricsChallenge',
   'GET returns 200 with text/plain content type','GET includes version info gauge after update loop runs',
   'GET includes per-difficulty and per-category challenge solved/total gauges','GET includes cheat score gauge',
   'GET includes coding challenge progress gauges for all three phases','GET includes registered user counts from update loop',
   'GET includes http request counter incremented by the request middleware',
   'GET includes file upload success counter after a valid upload',
   'GET includes file upload error counter after an upload that triggers a downstream error')],
 (USER,'POST new admin',['AMP2d60f2c545f1c37a','AMP8655da69167e4466'],PAPEL+' '+CADASTRO),
 (USER,'POST new deluxe user',['AMP2d60f2c545f1c37a','AMP8655da69167e4466'],PAPEL+' '+CADASTRO),
 (USER,'POST new accounting user',['AMP2d60f2c545f1c37a','AMP8655da69167e4466'],PAPEL+' '+CADASTRO),
 *[(USER,n,['AMP8655da69167e4466'],CADASTRO) for n in ('POST new user','POST new blank user','POST same blank user in database',
   'POST whitespaces user','POST user not belonging to customer, deluxe, accounting, admin is forbidden')],
 ('test/api/password.test.ts','GET password change for newly created user with recognized token as Authorization header',['AMP8655da69167e4466'],CADASTRO),
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def linha_do_teste(raiz, arquivo, nome):
    texto=(raiz/arquivo).read_text(encoding='utf-8').splitlines()
    for i,linha in enumerate(texto,1):
        if re.search(r"\bit\(",linha) and nome in linha:
            return i
    raise ValueError(f'Teste inexistente: {arquivo} :: {nome}')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--checkout',type=Path,default=RAIZ_REPO/'workspace/wt-1')
    args=ap.parse_args()
    for name in (DESTINO,REVISAO_NOVA,MAPA_NOVO):
        if (RAIZ_REPO/name).exists():
            ap.exit(1,f'ERRO: destino existente: {name}\n')
    casos={c['caso_id'] for c in json.loads((RAIZ_REPO/CATALOGO).read_text(encoding='utf-8'))}
    origem=json.loads((RAIZ_REPO/ORIGEM).read_text(encoding='utf-8'))
    globais={(d['arquivo'],d['nome']) for d in origem['d']}
    por_caso=[];vistos=set()
    for arquivo,nome,lista,motivo in ENTRADAS:
        raiz=RAIZ_REPO if arquivo.startswith('tests/') else args.checkout
        if set(lista)-casos or (arquivo,nome) in vistos or (arquivo,nome) in globais:
            ap.exit(1,f'ERRO: entrada inválida: {arquivo} :: {nome}\n')
        vistos.add((arquivo,nome))
        por_caso.append({'arquivo':arquivo,'casos':sorted(lista),'criterio':'d','linha_it':linha_do_teste(raiz,arquivo,nome),
                         'nome':nome,'observacao':motivo})
    novo=dict(origem,por_caso=por_caso,criterios_sha256=digest(RAIZ_REPO/CRITERIOS),origem_sha256=digest(RAIZ_REPO/ORIGEM))
    (RAIZ_REPO/DESTINO).write_text(json.dumps(novo,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    texto=(RAIZ_REPO/REVISAO).read_text(encoding='utf-8')
    anterior=f"  arquivo: {ORIGEM}\n  sha256: {digest(RAIZ_REPO/ORIGEM)}\n"
    if texto.count(anterior)!=1:
        ap.exit(1,'ERRO: referência do conjunto D não encontrada na revisão\n')
    (RAIZ_REPO/REVISAO_NOVA).write_text(texto.replace(anterior,f"  arquivo: {DESTINO}\n  sha256: {digest(RAIZ_REPO/DESTINO)}\n"),encoding='utf-8')
    mapa=(RAIZ_REPO/MAPA).read_text(encoding='utf-8')
    antigo=f"cobertura_sha256: {digest(RAIZ_REPO/REVISAO)}\n"
    if mapa.count(antigo)!=1:
        ap.exit(1,'ERRO: hash da revisão não encontrado no mapa\n')
    (RAIZ_REPO/MAPA_NOVO).write_text(mapa.replace(antigo,f"cobertura_sha256: {digest(RAIZ_REPO/REVISAO_NOVA)}\n"),encoding='utf-8')
    print(f'{len(por_caso)} testes ligados a {len({c for e in por_caso for c in e["casos"]})} casos')


if __name__=='__main__':raise SystemExit(main())
