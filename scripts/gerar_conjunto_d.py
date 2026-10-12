#!/usr/bin/env python3
"""Gera docs/conjunto_d.md e config/conjunto_d.json a partir dos criterios de
docs/criterios_conjunto_d.md, aplicados a test/api e test/server inteiros.

- Criterio (a) e detectado mecanicamente (asserção de desafio resolvido).
- Criterios (b) e (c) vem da revisao manual registrada em CLASSIFICACAO_MANUAL
  abaixo (arquivo, linha do it(...), criterio, linha da asserção, observacao).
  A revisao foi feita sobre a suite inteira, localizando candidatos por sinais
  de carga de ataque e por palavras-chave no nome, e decidindo pelas asserções.
- REJEITADOS lista o que foi examinado e ficou em F, com o motivo.

Uso:
    python scripts/gerar_conjunto_d.py
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WT = RAIZ / "workspace" / "wt-1"
SAIDA_MD = RAIZ / "docs" / "conjunto_d.md"
SAIDA_JSON = RAIZ / "config" / "conjunto_d.json"

IT = re.compile(r"""^\s*(?:void\s+)?it\(\s*(['"`])((?:\\.|(?!\1).)*)\1""", re.M)
DESAFIO = re.compile(r"assert\.equal\(\s*challenges?(\.\w+)?\.solved\s*,\s*true\s*\)"
                     r"|Challenge successfully solved")

# (arquivo, linha do it, criterio, linha da assercao, observacao)
CLASSIFICACAO_MANUAL = [
    ("test/api/basket.test.ts", 62, "b", 70, "JWT sem assinatura (alg none) aceito: 200"),
    ("test/api/basket.test.ts", 111, "b", 121, "cesta de outro usuario (IDOR) devolvida: 200"),
    ("test/api/basket.test.ts", 142, "b", 152, "pedido com total negativo confirmado"),
    ("test/api/basket.test.ts", 154, "b", 161, "cupom forjado com 99% de desconto aceito"),
    ("test/api/erasure-request.test.ts", 101, "b", 111, "layout '../package.json' devolve o arquivo"),
    ("test/api/feedback.test.ts", 52, "c", 68, "iframe javascript: gravado sem neutralizacao"),
    ("test/api/feedback.test.ts", 71, "b", 90, "feedback anonimo gravado em nome de outro usuario"),
    ("test/api/ftp-folder.test.ts", 86, "b", 92, "null byte (%2500) libera arquivo restrito"),
    ("test/api/ftp-folder.test.ts", 94, "b", 100, "null byte (%2500) libera arquivo restrito"),
    ("test/api/ftp-folder.test.ts", 102, "b", 108, "null byte (%2500) libera arquivo restrito"),
    ("test/api/ftp-folder.test.ts", 110, "b", 116, "null byte (%2500) libera arquivo restrito"),
    ("test/api/ftp-folder.test.ts", 118, "b", 124, "null byte (%2500) libera arquivo restrito"),
    ("test/api/ftp-folder.test.ts", 126, "b", 132, "null byte (%2500) libera arquivo restrito"),
    ("test/api/ftp-folder.test.ts", 134, "b", 140, "null byte (%2500) libera arquivo restrito"),
    ("test/api/ftp-folder.test.ts", 142, "b", 148, "null byte (%2500) libera arquivo restrito"),
    ("test/api/ftp-folder.test.ts", 182, "b", 188, "null byte (%2500) libera package.json.bak"),
    ("test/api/login.test.ts", 154, "b", 166, "SQL injection devolve token"),
    ("test/api/login.test.ts", 168, "b", 180, "SQL injection devolve token"),
    ("test/api/login.test.ts", 182, "b", 194, "SQL injection devolve token"),
    ("test/api/login.test.ts", 196, "b", 208, "SQL injection devolve token"),
    ("test/api/login.test.ts", 210, "b", 222, "UNION SELECT devolve token"),
    ("test/api/product-review.test.ts", 36, "b", 40, "injecao NoSQL sleep(1) aceita: 200"),
    ("test/api/product-review.test.ts", 125, "b", 141, "injecao NoSQL ($ne) altera todas as avaliacoes"),
    ("test/api/product.test.ts", 58, "c", 69, "iframe javascript: gravado sem neutralizacao"),
    ("test/api/redirect.test.ts", 100, "b", 105, "allowlist contornada pela query string: 200"),
    ("test/api/search.test.ts", 41, "c", 48, "vazamento de erro de SQL (SQLITE_ERROR)"),
    ("test/api/search.test.ts", 50, "c", 57, "vazamento de erro de SQL (SQLITE_ERROR)"),
    ("test/api/search.test.ts", 59, "c", 66, "vazamento de erro de SQL (SQLITE_ERROR)"),
    ("test/api/search.test.ts", 68, "c", 75, "vazamento de erro de SQL (SQLITE_ERROR)"),
    ("test/api/search.test.ts", 77, "b", 88, "UNION SELECT devolve linhas injetadas"),
    ("test/api/search.test.ts", 90, "b", 100, "UNION SELECT devolve usuarios e hashes"),
    ("test/api/search.test.ts", 127, "b", 137, "UNION SELECT devolve o esquema (sqlite_master)"),
    ("test/api/search.test.ts", 160, "b", 167, "comentario SQL devolve produto excluido"),
    ("test/api/search.test.ts", 169, "b", 176, "comentario SQL devolve produto excluido"),
    ("test/api/track-result.test.ts", 25, "b", 31, "injecao em orderId devolve todos os pedidos"),
    ("test/api/user-profile.test.ts", 64, "c", 79, "template avaliado (SSTI #{7*7} -> 49)"),
    ("test/api/user.test.ts", 183, "c", 193, "iframe javascript: gravado sem neutralizacao"),
    ("test/server/insecurity.unit.test.ts", 136, "c", 138, "sanitizacao contornada: script entregue"),
    ("test/server/insecurity.unit.test.ts", 157, "c", 159, "sanitizacao legada contornada: script entregue"),
]

# (arquivo, linha do it, motivo)
REJEITADOS = [
    # Fora dos tres criterios, mas parecem depender de uma falha: F pela regra
    # ("em duvida, F"). Sinalizados para decisao do grupo.
    ("test/api/file-serving.test.ts", 135, "SINALIZADO: listagem de diretorio sem carga de ataque (GET simples)"),
    ("test/api/ftp-folder.test.ts", 24, "SINALIZADO: listagem de diretorio sem carga de ataque (GET simples)"),
    ("test/api/file-serving.test.ts", 203, "SINALIZADO: log de acesso exposto, sem carga de ataque"),
    ("test/api/logfile-server.test.ts", 21, "SINALIZADO: log de acesso exposto, sem carga de ataque"),
    ("test/api/api.test.ts", 29, "SINALIZADO: vazamento de erro que nao e de SQL (fora do criterio c)"),
    ("test/api/redirect.test.ts", 69, "SINALIZADO: vazamento de erro que nao e de SQL (fora do criterio c)"),
    ("test/api/redirect.test.ts", 80, "SINALIZADO: vazamento de erro que nao e de SQL (fora do criterio c)"),
    ("test/api/erasure-request.test.ts", 89, "SINALIZADO: vazamento de erro do sistema de arquivos (fora do criterio c)"),
    ("test/api/file-upload.test.ts", 123, "SINALIZADO: zip com traversal devolve 204, mas uma implementacao segura tambem pode devolver 204"),
    ("test/api/b2b-order.test.ts", 36, "SINALIZADO: ReDoS devolve 503; nao afirma sucesso do ataque"),
    ("test/api/data-export.test.ts", 51, "SINALIZADO: exportacao sem CAPTCHA; sem carga de ataque"),
    ("test/api/data-export.test.ts", 71, "SINALIZADO: exportacao sem CAPTCHA; sem carga de ataque"),
    # Afirmam que a defesa funciona ou que a carga nao teve efeito: F.
    ("test/api/b2b-order.test.ts", 25, "defesa: loop infinito detectado (500)"),
    ("test/api/b2b-order.test.ts", 47, "defesa: sandbox breakout gera erro (500)"),
    ("test/api/challenge.test.ts", 95, "defesa: carga XSS rejeitada (404)"),
    ("test/api/feedback.test.ts", 31, "defesa: HTML inseguro removido"),
    ("test/api/file-serving.test.ts", 51, "carga de traversal sem efeito: devolve index.html"),
    ("test/api/file-serving.test.ts", 154, "defesa: barra no nome rejeitada (403)"),
    ("test/api/file-upload.test.ts", 64, "XXE: upload XML descontinuado (410)"),
    ("test/api/file-upload.test.ts", 71, "XXE: upload XML descontinuado (410)"),
    ("test/api/file-upload.test.ts", 79, "defesa: Billion Laughs detectado pelo parser"),
    ("test/api/ftp-folder.test.ts", 162, "defesa: barra no nome rejeitada (403)"),
    ("test/api/login.test.ts", 224, "defesa: SQL que quebra a consulta devolve 401"),
    ("test/api/quarantine-server.test.ts", 26, "defesa: barra no nome rejeitada (403)"),
    ("test/api/search.test.ts", 152, "carga sem efeito: produto excluido nao aparece"),
    ("test/api/security-question.test.ts", 99, "defesa: nao suscetivel a SQL injection"),
    ("test/api/user-profile.test.ts", 81, "vale com ou sem a falha: nome exibido literalmente"),
    ("test/server/insecurity.unit.test.ts", 130, "defesa: sanitizacao remove scripts"),
    ("test/server/insecurity.unit.test.ts", 179, "defesa: sanitizacao segura remove scripts"),
    ("test/server/insecurity.unit.test.ts", 185, "defesa: sanitizacao segura nao e contornada"),
    ("test/server/xml.unit.test.ts", 33, "defesa: bomba de entidades interrompida"),
    ("test/server/fileServer.unit.test.ts", 27, "mock do caminho de chamada (sendFile): F por definicao"),
    ("test/server/fileServer.unit.test.ts", 36, "mock do caminho de chamada (sendFile): F por definicao"),
    ("test/server/fileServer.unit.test.ts", 45, "mock do caminho de chamada (sendFile): F por definicao"),
    ("test/server/keyServer.unit.test.ts", 21, "mock do caminho de chamada (sendFile): F por definicao"),
]


def todos_os_its():
    for pasta in ("test/api", "test/server"):
        for arq in sorted((WT / pasta).rglob("*.ts")):
            if "/helpers/" in arq.as_posix():
                continue
            texto = arq.read_text(encoding="utf-8")
            ms = list(IT.finditer(texto))
            for k, m in enumerate(ms):
                fim = ms[k + 1].start() if k + 1 < len(ms) else len(texto)
                corpo = texto[m.start():fim]
                d = re.search(r"\n\s*(?:void\s+)?describe\(", corpo[1:])
                if d:
                    corpo = corpo[:d.start() + 1]
                # Linha do proprio it(...): conta a partir do nome, porque o
                # '^\s*' do padrao pode comecar na linha em branco anterior.
                linha = texto.count("\n", 0, m.start(2)) + 1
                nome = m.group(2).replace("\\'", "'").replace('\\"', '"')
                inicio_corpo = texto.count("\n", 0, m.start()) + 1
                yield arq.relative_to(WT).as_posix(), linha, nome, corpo, inicio_corpo


def main() -> None:
    its = list(todos_os_its())
    por_pos = {(a, l): (n, c) for a, l, n, c, _ in its}
    lista = []
    for a, l, n, c, ini in its:
        m = DESAFIO.search(c)
        if m:
            la = ini + c[:m.start()].count("\n")
            lista.append({"arquivo": a, "linha_it": l, "nome": n, "criterio": "a",
                          "linha_assercao": la, "observacao": "asserção de desafio resolvido"})
    def resolver(a: str, l: int) -> int:
        # As linhas da revisao manual foram anotadas com o deslocamento antigo
        # (linha em branco anterior); aceita l ou l+1 e grava a linha real.
        for cand in (l, l + 1):
            if (a, cand) in por_pos:
                return cand
        raise SystemExit(f"it(...) nao encontrado em {a}:{l}")

    vistos = {(x["arquivo"], x["linha_it"]) for x in lista}
    for a, l, crit, la, obs in CLASSIFICACAO_MANUAL:
        l = resolver(a, l)
        if (a, l) in vistos:
            raise SystemExit(f"{a}:{l} ja esta em D pelo criterio (a)")
        n, c = por_pos[(a, l)]
        if not (l <= la < l + c.count("\n") + 1):
            raise SystemExit(f"linha da assercao {la} fora do bloco {a}:{l}")
        lista.append({"arquivo": a, "linha_it": l, "nome": n, "criterio": crit,
                      "linha_assercao": la, "observacao": obs})
    rej = []
    for a, l, motivo in REJEITADOS:
        l = resolver(a, l)
        rej.append({"arquivo": a, "linha_it": l, "nome": por_pos[(a, l)][0], "motivo": motivo})
    lista.sort(key=lambda x: (x["arquivo"], x["linha_it"]))

    dados = {
        "gerado_em": date.today().isoformat(),
        "fonte_criterios": "docs/criterios_conjunto_d.md",
        "commit_alvo_varrido": "f915bddd82790d0f3018902d36ae9b4241a5f51f",
        "its_varridos": len(its),
        "d": lista,
        "rejeitados": rej,
    }
    SAIDA_JSON.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cont = {k: sum(1 for x in lista if x["criterio"] == k) for k in "abc"}
    linhas = [
        "# Conjunto D: lista de testes",
        "",
        f"Gerado por `scripts/gerar_conjunto_d.py` em {dados['gerado_em']}, a partir de "
        "`docs/criterios_conjunto_d.md`. Versão legível por máquina: `config/conjunto_d.json`.",
        "",
        f"Varredura: **{len(its)} blocos `it(...)`** de `test/api/` e `test/server/` inteiros, no commit "
        "`f915bddd`. Os ~27 testes gerados em laço (`redirect.unit.test.ts`, um por URL permitida) são "
        "funcionais e ficam em F. A lista foi montada sobre a suíte, sem consultar resultados de execução.",
        "",
        f"**Total em D: {len(lista)}** — critério (a): {cont['a']}; (b): {cont['b']}; (c): {cont['c']}.",
        "",
        "`d_marcador` usa só os testes do critério (a); `d_criterio` usa a lista inteira.",
        "",
        "## Testes em D",
        "",
        "| Arquivo | Linha do `it` | Nome do `it(...)` | Critério | Linha da asserção | Observação |",
        "|---|---:|---|:-:|---:|---|",
    ]
    for x in lista:
        nome = x["nome"].replace("|", "\\|")
        linhas.append(f"| `{x['arquivo']}` | {x['linha_it']} | {nome} | ({x['criterio']}) | "
                      f"{x['linha_assercao']} | {x['observacao']} |")
    linhas += [
        "",
        "## Examinados e mantidos em F",
        "",
        "Testes que parecem de ataque mas não cumprem nenhum dos três critérios. Os marcados como "
        "**SINALIZADO** parecem depender de uma falha, mas ficam fora da letra dos critérios; "
        "pela regra \"em dúvida, F\", ficam em F, e ficam listados para decisão do grupo.",
        "",
        "| Arquivo | Linha do `it` | Nome do `it(...)` | Motivo |",
        "|---|---:|---|---|",
    ]
    for x in rej:
        nome = (x["nome"] or "").replace("|", "\\|")
        linhas.append(f"| `{x['arquivo']}` | {x['linha_it']} | {nome} | {x['motivo']} |")
    SAIDA_MD.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"its varridos: {len(its)} | D: {len(lista)} {cont} | rejeitados: {len(rej)}")
    print(f"-> {SAIDA_MD.relative_to(RAIZ)}, {SAIDA_JSON.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
