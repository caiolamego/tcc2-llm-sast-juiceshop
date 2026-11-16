#!/usr/bin/env python3
"""Gera o conjunto D v3, a revisão de cobertura v8 e o mapa v9, sem LLM e sem sobrescrever.

Acrescenta o critério (e), que vale em todos os casos, amplia o critério (d) e publica o
grupo de contratos legítimos. Recusa teste inexistente, caso fora do catálogo e destino existente.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import _bootstrap  # noqa: F401,E402
import argparse
import hashlib
import json
import re
import yaml
from pipeline.comum.caminhos import RAIZ_REPO
from pipeline.etapas.e07_validacao.cobertura import derivar_mapa, ler_yaml

ORIGEM='config/conjunto_d_cobertura_v2.json'
DESTINO='config/conjunto_d_cobertura_v3.json'
REVISAO='config/cobertura_funcional_v7.yaml'
REVISAO_NOVA='config/cobertura_funcional_v8.yaml'
MAPA_NOVO='config/mapa_testes_relacionados_v9.yaml'
CATALOGO='outputs/catalogos/ampliado_v1/catalogo_issues.json'
CRITERIOS='docs/criterios_conjunto_d.md'
CONTRATOS='tests/functional/juice_shop/contratos_legitimos.test.ts'
STARTUP='tests/functional/juice_shop/server_startup.unit.test.ts'

FEEDBACK='test/api/feedback.test.ts'
PROFILE='test/api/profile-image-upload.test.ts'
RESPOSTA='Usa o answer devolvido pelo servidor para preparar o teste: exige o vazamento.'
LOCAL='Baixa a imagem de localhost: exige que o servidor acesse endereços internos.'
SCRIPT='Exige as legendas dentro da tag script apontada pelo alerta.'
ERRO='Exige a mensagem de erro interna na resposta.'
AVALIA='O erro só existe se o código enviado pelo cliente for avaliado.'

# (arquivo, nome, trecho da asserção, justificativa). Critério (e): vale em todos os casos.
TODOS_OS_CASOS=[
 ('test/api/product.test.ts','PUT update existing product is possible due to Missing Function-Level Access Control vulnerability',
  'assert.equal(res.status, 200)','Altera um produto sem credencial e espera sucesso.'),
 ('test/api/user.test.ts','GET who-am-i with fields parameter can be tricked into returning password',
  "assert.equal(typeof res.body.user.password, 'string')",'Exige que a resposta traga a senha.'),
 ('test/api/ftp-folder.test.ts','GET serves a directory listing',"listing directory /ftp",'Exige a página de listagem de /ftp.'),
 ('test/api/file-serving.test.ts','GET serves a directory listing','listing directory /encryptionkeys','Exige a página de listagem de /encryptionkeys.'),
 ('test/api/file-serving.test.ts','GET folder containing access log files for "Access Log" challenge','assert.equal(res.status, 200)','Exige baixar o log de acesso sem credencial.'),
 ('test/api/logfile-server.test.ts','GET access log file for the current day','assert.equal(res.status, 200)','Exige baixar o log de acesso sem credencial.'),
 ('test/api/redirect.test.ts','GET error message with information leakage when calling /redirect without query parameter',"includes('TypeError')",ERRO),
 ('test/api/redirect.test.ts','GET error message with information leakage when calling /redirect with unrecognized query parameter',"includes('TypeError')",ERRO),
 ('test/api/api.test.ts','GET error message with information leakage when calling unrecognized path with /rest in it','Unexpected path',ERRO),
 ('test/api/erasure-request.test.ts','POST erasure request with non-existing file path as layout parameter throws error','no such file or directory','Exige que o layout do cliente chegue ao sistema de arquivos.'),
 ('test/api/b2b-order.test.ts','POST sandbox breakout attack in "orderLinesData" will raise error','assert.equal(res.status, 500)',AVALIA),
 ('test/api/b2b-order.test.ts','POST endless loop exploit in "orderLinesData" will raise explicit error','Infinite loop detected',AVALIA),
 ('test/api/b2b-order.test.ts','POST busy spinning regex attack does not raise an error','assert.equal(res.status, 503)',AVALIA),
]

# (arquivo, nome, casos, justificativa). Critério (d): vale só nos casos listados.
POR_CASO_NOVOS=[
 ('test/api/basket.test.ts','should return 500 if QuantityModel.findOne fails during checkout',['AMPbd16f473e192b7d4'],'bjoern fecha o carrinho 4, da amy, e espera chegar à consulta de estoque.'),
 (FEEDBACK,'POST feedback is associated with current user',['AMP4d38adc404310ebe'],RESPOSTA),
 (FEEDBACK,'POST feedback is associated with any passed user ID',['AMP4d38adc404310ebe'],RESPOSTA),
 ('tests/functional/juice_shop/campaign_discount.test.ts','does not discount a campaign with a mismatched date',['AMPab8d19b259bd5d75'],'Exige que a data enviada pelo cliente continue decidindo o desconto.'),
 ('test/api/product-review.test.ts','PATCH single product review can be edited',['AMP3d463bdbd0a7b446','AMP4a7e01977b7eba72'],'Token sem usuário edita a avaliação de outra pessoa e espera sucesso.'),
 ('frontend/src/app/about/about.component.spec.ts','should cycle through the available carousel images when there are more feedbacks than images',['AMP746c0b4d1a2f8ed4'],'O mock só oferece bypassSecurityTrustHtml, que é o sink apontado pelo alerta.'),
 *[(PROFILE,n,['AMPf6324e7620b8e159'],LOCAL) for n in (
   'POST with non-OK response falls back to storing URL as profile image',
   'POST with empty-body response (204) falls back to storing URL as profile image',
   'POST with valid response writes file and redirects to profile',
   'POST with PNG URL extension saves file using PNG extension',
   'POST with unrecognised URL extension defaults to JPG extension')],
 ('test/api/promotion-video.test.ts','GET promotion video page contains subtitles as <script>',['AMP5936615902690208','AMPf50218b7fbd39171','AMPc0372089a0f8df39'],SCRIPT),
 ('test/server/xml.unit.test.ts','should expand internal entities',['AMPf7a5e2edd454d398'],'Exige a expansão de entidades que o alerta manda desligar.'),
 ('test/api/basket-item.test.ts','PUT update basket ID of basket item without basket ID',['AMPaf88892821bf5a51','AMPba6a42f81dbc573f'],'jim move um item para o carrinho 3, do bender, e espera sucesso.'),
]
# Caso acrescentado a uma entrada que já existia na versão 2.
AMPLIAR=[(FEEDBACK,'POST feedback in a non-existing users name as anonymous user fails with constraint error',
          'AMPff4689848e9b84b8','Envia rating 0: exige que a nota continue sem limite mínimo.')]
CONTRATOS_NOMES=['lets the author edit their own review','answers an error without a location to a redirect without target',
                 'stores the image of a public URL as the profile image']
CASOS_CONTRATOS={'AMP3d463bdbd0a7b446','AMP4a7e01977b7eba72','AMP7f162887aff2d750','AMPf6324e7620b8e159'}


class SemAlias(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def linha_do_teste(raiz, arquivo, nome):
    linhas=(raiz/arquivo).read_text(encoding='utf-8').splitlines()
    achadas=[i for i,l in enumerate(linhas,1) if nome in l]
    com_it=[i for i in achadas if re.search(r"\bit\(",linhas[i-1])]
    if com_it:return com_it[0]
    if achadas and arquivo.startswith('tests/'):return achadas[0]  # Cenários declarados em tabela.
    raise ValueError(f'Teste inexistente: {arquivo} :: {nome}')


def linha_da_assercao(raiz, arquivo, linha_it, trecho):
    linhas=(raiz/arquivo).read_text(encoding='utf-8').splitlines()
    for i in range(linha_it,len(linhas)+1):
        if trecho in linhas[i-1]:return i
    raise ValueError(f'Asserção inexistente: {arquivo}:{linha_it} :: {trecho}')


def assercoes(path):
    return [{'linha':i,'texto':l.strip()} for i,l in enumerate(Path(path).read_text(encoding='utf-8').splitlines(),1) if 'assert.' in l]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--checkout',type=Path,default=RAIZ_REPO/'workspace/wt-1')
    args=ap.parse_args()
    for name in (DESTINO,REVISAO_NOVA,MAPA_NOVO):
        if (RAIZ_REPO/name).exists():
            ap.exit(1,f'ERRO: destino existente: {name}\n')
    casos={c['caso_id'] for c in json.loads((RAIZ_REPO/CATALOGO).read_text(encoding='utf-8'))}
    origem=json.loads((RAIZ_REPO/ORIGEM).read_text(encoding='utf-8'))
    movidos={(a,n) for a,n,_,_ in TODOS_OS_CASOS}
    globais=list(origem['d'])
    if movidos&{(d['arquivo'],d['nome']) for d in globais}:
        ap.exit(1,'ERRO: teste já global\n')
    for arquivo,nome,trecho,motivo in TODOS_OS_CASOS:
        linha=linha_do_teste(args.checkout,arquivo,nome)
        globais.append({'arquivo':arquivo,'criterio':'e','linha_assercao':linha_da_assercao(args.checkout,arquivo,linha,trecho),
                        'linha_it':linha,'nome':nome,'observacao':motivo})
    por_caso=[dict(e) for e in origem['por_caso'] if (e['arquivo'],e['nome']) not in movidos]
    for arquivo,nome,caso,motivo in AMPLIAR:
        alvo=[e for e in por_caso if (e['arquivo'],e['nome'])==(arquivo,nome)]
        if len(alvo)!=1 or caso not in casos:ap.exit(1,f'ERRO: entrada inválida: {nome}\n')
        alvo[0]['casos']=sorted(set(alvo[0]['casos'])|{caso});alvo[0]['observacao']+=' '+motivo
    existentes={(e['arquivo'],e['nome']) for e in por_caso}|{(d['arquivo'],d['nome']) for d in globais}
    for arquivo,nome,lista,motivo in POR_CASO_NOVOS:
        raiz=RAIZ_REPO if arquivo.startswith('tests/') else args.checkout
        if set(lista)-casos or (arquivo,nome) in existentes:
            ap.exit(1,f'ERRO: entrada inválida: {arquivo} :: {nome}\n')
        existentes.add((arquivo,nome))
        por_caso.append({'arquivo':arquivo,'casos':sorted(lista),'criterio':'d','linha_it':linha_do_teste(raiz,arquivo,nome),
                         'nome':nome,'observacao':motivo})
    novo=dict(origem,d=globais,por_caso=por_caso,criterios_sha256=digest(RAIZ_REPO/CRITERIOS),origem_sha256=digest(RAIZ_REPO/ORIGEM))
    (RAIZ_REPO/DESTINO).write_text(json.dumps(novo,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

    revisao=ler_yaml(RAIZ_REPO/REVISAO)
    revisao['conjunto_d']={'arquivo':DESTINO,'sha256':digest(RAIZ_REPO/DESTINO)}
    startup=revisao['grupos']['server_startup']
    startup['testes'][0]['sha256']=digest(RAIZ_REPO/STARTUP)
    startup['evidencias']=[{'arquivo':STARTUP,'assercoes':assercoes(RAIZ_REPO/STARTUP)}]
    if 'contratos_legitimos' in revisao['grupos']:ap.exit(1,'ERRO: grupo já existe\n')
    revisao['grupos']['contratos_legitimos']={
        'dominio':'api','compilacoes':['servidor'],
        'testes':[{'origem':'avaliacao','arquivo':CONTRATOS,'destino':'test/api/tcc_coverage_contratos_legitimos.test.ts','sha256':digest(RAIZ_REPO/CONTRATOS)}],
        'comportamentos':['Edição da própria avaliação, recusa de redirecionamento sem destino e imagem de perfil por URL pública'],
        'obrigatorios':[{'arquivo':CONTRATOS,'nome':n} for n in CONTRATOS_NOMES],
        'evidencias':[{'arquivo':CONTRATOS,'assercoes':assercoes(RAIZ_REPO/CONTRATOS)}],
        'limitacoes':['A imagem de perfil simula só a resposta externa; correção que não use fetch precisa de revisão manual.']}
    ligados=set()
    for caso in revisao['casos']:
        if caso['caso_id'] in CASOS_CONTRATOS:
            caso['grupos']=sorted(set(caso['grupos'])|{'contratos_legitimos'});ligados.add(caso['caso_id'])
    if ligados!=CASOS_CONTRATOS:ap.exit(1,'ERRO: caso de contrato ausente\n')
    revisao['priorizacao']={'grupos_adicionados_nesta_revisao':['contratos_legitimos'],
                            'justificativa':'Testes que exigiam a vulnerabilidade saíram de F (conjunto D v3); o comportamento legítimo que eles também cobriam passou para contratos que valem com e sem a falha.'}
    texto=yaml.dump(revisao,Dumper=SemAlias,allow_unicode=True,sort_keys=False,width=120)
    (RAIZ_REPO/REVISAO_NOVA).write_text(texto,encoding='utf-8')
    mapa=derivar_mapa(revisao,digest(RAIZ_REPO/REVISAO_NOVA))
    (RAIZ_REPO/MAPA_NOVO).write_text(yaml.dump(mapa,Dumper=SemAlias,allow_unicode=True,sort_keys=False,width=120),encoding='utf-8')
    print(f'{len(globais)} testes em todos os casos e {len(por_caso)} ligados a {len({c for e in por_caso for c in e["casos"]})} casos')


if __name__=='__main__':raise SystemExit(main())
