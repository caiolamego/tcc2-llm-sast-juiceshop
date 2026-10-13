# Conjunto D: lista de testes

Gerado por `scripts/experiment/gerar_conjunto_d.py` em 2026-10-09, a partir de `docs/criterios_conjunto_d.md`. Versão legível por máquina: `config/conjunto_d.json`.

Varredura: **863 blocos `it(...)`** de `test/api/` e `test/server/` inteiros, no commit `f915bddd`. Os ~27 testes gerados em laço (`redirect.unit.test.ts`, um por URL permitida) são funcionais e ficam em F. A lista foi montada sobre a suíte, sem consultar resultados de execução.

**Total em D: 75** — critério (a): 36; (b): 29; (c): 10.

`d_marcador` usa só os testes do critério (a); `d_criterio` usa a lista inteira.

## Testes em D

| Arquivo | Linha do `it` | Nome do `it(...)` | Critério | Linha da asserção | Observação |
|---|---:|---|:-:|---:|---|
| `test/api/basket.test.ts` | 63 | GET basket should accept forged JWTs | (b) | 70 | JWT sem assinatura (alg none) aceito: 200 |
| `test/api/basket.test.ts` | 111 | GET existing basket of another user | (b) | 121 | cesta de outro usuario (IDOR) devolvida: 200 |
| `test/api/basket.test.ts` | 143 | POST placing an order for a basket with a negative total cost is possible | (b) | 152 | pedido com total negativo confirmado |
| `test/api/basket.test.ts` | 155 | POST placing an order for a basket with 99% discount is possible | (b) | 161 | cupom forjado com 99% de desconto aceito |
| `test/api/checkKeys.test.ts` | 65 | POST private key in request body gets accepted | (a) | 73 | asserção de desafio resolvido |
| `test/api/erasure-request.test.ts` | 102 | POST erasure request with existing file path as layout parameter returns content truncated | (b) | 111 | layout '../package.json' devolve o arquivo |
| `test/api/feedback.test.ts` | 52 | POST fails to sanitize masked XSS-attack by not applying sanitization recursively | (c) | 68 | iframe javascript: gravado sem neutralizacao |
| `test/api/feedback.test.ts` | 72 | POST feedback in another users name as anonymous user | (b) | 90 | feedback anonimo gravado em nome de outro usuario |
| `test/api/ftp-folder.test.ts` | 87 | GET the easter egg file by using Poison Null Byte attack with .pdf suffix | (b) | 92 | null byte (%2500) libera arquivo restrito |
| `test/api/ftp-folder.test.ts` | 95 | GET the easter egg file by using Poison Null Byte attack with .md suffix | (b) | 100 | null byte (%2500) libera arquivo restrito |
| `test/api/ftp-folder.test.ts` | 103 | GET the SIEM signature file by using Poison Null Byte attack with .pdf suffix | (b) | 108 | null byte (%2500) libera arquivo restrito |
| `test/api/ftp-folder.test.ts` | 111 | GET the SIEM signature file by using Poison Null Byte attack with .md suffix | (b) | 116 | null byte (%2500) libera arquivo restrito |
| `test/api/ftp-folder.test.ts` | 119 | GET the 2013 coupon code file by using Poison Null Byte attack with .pdf suffix | (b) | 124 | null byte (%2500) libera arquivo restrito |
| `test/api/ftp-folder.test.ts` | 127 | GET the 2013 coupon code file by using an Poison Null Byte attack with .md suffix | (b) | 132 | null byte (%2500) libera arquivo restrito |
| `test/api/ftp-folder.test.ts` | 135 | GET the package.json.bak file by using Poison Null Byte attack with .pdf suffix | (b) | 140 | null byte (%2500) libera arquivo restrito |
| `test/api/ftp-folder.test.ts` | 143 | GET the package.json.bak file by using Poison Null Byte attack with .md suffix | (b) | 148 | null byte (%2500) libera arquivo restrito |
| `test/api/ftp-folder.test.ts` | 183 | GET the package.json.bak file contains a dependency on epilogue-js for "Typosquatting" challenge | (b) | 188 | null byte (%2500) libera package.json.bak |
| `test/api/login.test.ts` | 155 | POST login with WHERE-clause disabling SQL injection attack | (b) | 166 | SQL injection devolve token |
| `test/api/login.test.ts` | 169 | POST login with known email "admin@juice-sh.op" in SQL injection attack | (b) | 180 | SQL injection devolve token |
| `test/api/login.test.ts` | 183 | POST login with known email "jim@juice-sh.op" in SQL injection attack | (b) | 194 | SQL injection devolve token |
| `test/api/login.test.ts` | 197 | POST login with known email "bender@juice-sh.op" in SQL injection attack | (b) | 208 | SQL injection devolve token |
| `test/api/login.test.ts` | 211 | POST login with non-existing email "acc0unt4nt@juice-sh.op" via UNION SELECT injection attack | (b) | 222 | UNION SELECT devolve token |
| `test/api/metrics.test.ts` | 64 | GET with a regular browser user agent solves exposedMetricsChallenge | (a) | 69 | asserção de desafio resolvido |
| `test/api/nftMint.test.ts` | 78 | POST minted wallet address successfully solves minting challenge | (a) | 98 | asserção de desafio resolvido |
| `test/api/product-review.test.ts` | 37 | GET product reviews attack by injecting a mongoDB sleep command | (b) | 40 | injecao NoSQL sleep(1) aceita: 200 |
| `test/api/product-review.test.ts` | 126 | PATCH multiple product review via injection | (b) | 141 | injecao NoSQL ($ne) altera todas as avaliacoes |
| `test/api/product.test.ts` | 58 | POST new product does not filter XSS attacks | (c) | 69 | iframe javascript: gravado sem neutralizacao |
| `test/api/redirect.test.ts` | 101 | GET redirected to target URL in "to" parameter when a allow-listed URL is part of the query string | (b) | 105 | allowlist contornada pela query string: 200 |
| `test/api/search.test.ts` | 42 | GET product search fails with error message that exposes ins SQL Injection vulnerability | (c) | 48 | vazamento de erro de SQL (SQLITE_ERROR) |
| `test/api/search.test.ts` | 51 | GET product search SQL Injection fails from two missing closing parenthesis | (c) | 57 | vazamento de erro de SQL (SQLITE_ERROR) |
| `test/api/search.test.ts` | 60 | GET product search SQL Injection fails from one missing closing parenthesis | (c) | 66 | vazamento de erro de SQL (SQLITE_ERROR) |
| `test/api/search.test.ts` | 69 | GET product search SQL Injection fails for SELECT * FROM attack due to wrong number of returned columns | (c) | 75 | vazamento de erro de SQL (SQLITE_ERROR) |
| `test/api/search.test.ts` | 78 | GET product search can create UNION SELECT with Users table and fixed columns | (b) | 88 | UNION SELECT devolve linhas injetadas |
| `test/api/search.test.ts` | 91 | GET product search can create UNION SELECT with Users table and required columns | (b) | 100 | UNION SELECT devolve usuarios e hashes |
| `test/api/search.test.ts` | 128 | GET product search can create UNION SELECT with sqlite_master table and required column | (b) | 137 | UNION SELECT devolve o esquema (sqlite_master) |
| `test/api/search.test.ts` | 161 | GET product search can select logically deleted christmas special by forcibly commenting out the remainder of where clause | (b) | 167 | comentario SQL devolve produto excluido |
| `test/api/search.test.ts` | 170 | GET product search can select logically deleted unsafe product by forcibly commenting out the remainder of where clause | (b) | 176 | comentario SQL devolve produto excluido |
| `test/api/track-result.test.ts` | 26 | GET all orders by injecting into orderId | (b) | 31 | injecao em orderId devolve todos os pedidos |
| `test/api/user-profile.test.ts` | 65 | GET user profile renders evaluated SSTI payload for username containing valid expression | (c) | 79 | template avaliado (SSTI #{7*7} -> 49) |
| `test/api/user.test.ts` | 183 | POST new user with XSS attack in email address | (c) | 193 | iframe javascript: gravado sem neutralizacao |
| `test/server/b2bOrder.unit.test.ts` | 28 | infinite loop payload does not succeed but solves "rceChallenge" | (a) | 33 | asserção de desafio resolvido |
| `test/server/b2bOrder.unit.test.ts` | 36 | timeout after 2 seconds solves "rceOccupyChallenge" | (a) | 41 | asserção de desafio resolvido |
| `test/server/challengeUtils.unit.test.ts` | 65 | should mark challenge as solved and save it | (a) | 81 | asserção de desafio resolvido |
| `test/server/challengeUtils.unit.test.ts` | 135 | should solve challenge if criteria is met and not yet solved | (a) | 147 | asserção de desafio resolvido |
| `test/server/easterEgg.unit.test.ts` | 32 | should solve "easterEggLevelTwoChallenge" | (a) | 37 | asserção de desafio resolvido |
| `test/server/fileServer.unit.test.ts` | 74 | should solve "directoryListingChallenge" when requesting acquisitions.md | (a) | 82 | asserção de desafio resolvido |
| `test/server/fileServer.unit.test.ts` | 85 | should solve "easterEggLevelOneChallenge" when requesting eastere.gg with Poison Null Byte attack | (a) | 93 | asserção de desafio resolvido |
| `test/server/fileServer.unit.test.ts` | 96 | should solve "forgottenDevBackupChallenge" when requesting package.json.bak with Poison Null Byte attack | (a) | 104 | asserção de desafio resolvido |
| `test/server/fileServer.unit.test.ts` | 107 | should solve "forgottenBackupChallenge" when requesting coupons_2013.md.bak with Poison Null Byte attack | (a) | 115 | asserção de desafio resolvido |
| `test/server/fileServer.unit.test.ts` | 118 | should solve "misplacedSignatureFileChallenge" when requesting suspicious_errors.yml with Poison Null Byte attack | (a) | 126 | asserção de desafio resolvido |
| `test/server/fileUpload.unit.test.ts` | 39 | should solve "uploadSizeChallenge" when file size exceeds 100000 bytes | (a) | 45 | asserção de desafio resolvido |
| `test/server/fileUpload.unit.test.ts` | 48 | should solve "uploadTypeChallenge" when file type is not PDF | (a) | 54 | asserção de desafio resolvido |
| `test/server/insecurity.unit.test.ts` | 137 | can be bypassed by exploiting lack of recursive sanitization | (c) | 138 | sanitizacao contornada: script entregue |
| `test/server/insecurity.unit.test.ts` | 158 | can be bypassed to allow working HTML payload to be returned | (c) | 159 | sanitizacao legada contornada: script entregue |
| `test/server/premiumReward.unit.test.ts` | 32 | should solve "premiumPaywallChallenge" | (a) | 37 | asserção de desafio resolvido |
| `test/server/redirect.unit.test.ts` | 51 | redirecting to https://blockchain.info/address/1AbKfgvw9psQ41NbLi8kufDQTezwG8DRZm should solve the "redirectCryptoCurrencyChallenge" | (a) | 57 | asserção de desafio resolvido |
| `test/server/redirect.unit.test.ts` | 60 | redirecting to https://explorer.dash.org/address/Xr556RzuwX6hg5EGpkybbv5RanJoZN17kW should solve the "redirectCryptoCurrencyChallenge" | (a) | 66 | asserção de desafio resolvido |
| `test/server/redirect.unit.test.ts` | 69 | redirecting to https://etherscan.io/address/0x0f933ab9fcaaa782d0279c300d73750e1311eae6 should solve the "redirectCryptoCurrencyChallenge" | (a) | 75 | asserção de desafio resolvido |
| `test/server/redirect.unit.test.ts` | 78 | tricking the allowlist should solve "redirectChallenge" | (a) | 84 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 62 | is solved when an authenticated user passes someone elses ID when writing feedback | (a) | 68 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 71 | is solved when an unauthenticated user passes someones ID when writing feedback | (a) | 77 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 82 | "scoreBoardChallenge" is solved when the 1px.png transpixel is requested | (a) | 88 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 91 | "adminSectionChallenge" is solved when the 19px.png transpixel is requested | (a) | 97 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 100 | "tokenSaleChallenge" is solved when the 56px.png transpixel is requested | (a) | 106 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 109 | "extraLanguageChallenge" is solved when the Klingon translation file is requested | (a) | 115 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 118 | "retrieveBlueprintChallenge" is solved when the blueprint file is requested | (a) | 125 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 128 | "missingEncodingChallenge" is solved when the crazy cat photo is requested | (a) | 134 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 137 | "accessLogDisclosureChallenge" is solved when any server access log file is requested | (a) | 143 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 152 | is solved when an error occurs on a response with OK 200 status code | (a) | 158 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 164 | ${statusCode} status code | (a) | 170 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 216 | is solved when the link in the O-Saft product goes to ${config.get<string>('challenges.overwriteUrlForProductTamperingChallenge')} | (a) | 221 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 255 | "jwtUnsignedChallenge" is solved when forged unsigned token has email jwtn3d@juice-sh.op in the payload | (a) | 260 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 263 | "jwtUnsignedChallenge" is solved when forged unsigned token has string "jwtn3d@" in the payload | (a) | 268 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 280 | "jwtForgedChallenge" is solved when forged token HMAC-signed with public RSA-key has email rsa_lord@juice-sh.op in the payload | (a) | 285 | asserção de desafio resolvido |
| `test/server/verify.unit.test.ts` | 288 | "jwtForgedChallenge" is solved when forged token HMAC-signed with public RSA-key has string "rsa_lord@" in the payload | (a) | 293 | asserção de desafio resolvido |

## Examinados e mantidos em F

Testes que parecem de ataque mas não cumprem nenhum dos três critérios. Os marcados como **SINALIZADO** parecem depender de uma falha, mas ficam fora da letra dos critérios; pela regra "em dúvida, F", ficam em F, e ficam listados para decisão do grupo.

| Arquivo | Linha do `it` | Nome do `it(...)` | Motivo |
|---|---:|---|---|
| `test/api/file-serving.test.ts` | 135 | GET serves a directory listing | SINALIZADO: listagem de diretorio sem carga de ataque (GET simples) |
| `test/api/ftp-folder.test.ts` | 24 | GET serves a directory listing | SINALIZADO: listagem de diretorio sem carga de ataque (GET simples) |
| `test/api/file-serving.test.ts` | 204 | GET folder containing access log files for "Access Log" challenge | SINALIZADO: log de acesso exposto, sem carga de ataque |
| `test/api/logfile-server.test.ts` | 21 | GET access log file for the current day | SINALIZADO: log de acesso exposto, sem carga de ataque |
| `test/api/api.test.ts` | 29 | GET error message with information leakage when calling unrecognized path with /rest in it | SINALIZADO: vazamento de erro que nao e de SQL (fora do criterio c) |
| `test/api/redirect.test.ts` | 70 | GET error message with information leakage when calling /redirect without query parameter | SINALIZADO: vazamento de erro que nao e de SQL (fora do criterio c) |
| `test/api/redirect.test.ts` | 81 | GET error message with information leakage when calling /redirect with unrecognized query parameter | SINALIZADO: vazamento de erro que nao e de SQL (fora do criterio c) |
| `test/api/erasure-request.test.ts` | 90 | POST erasure request with non-existing file path as layout parameter throws error | SINALIZADO: vazamento de erro do sistema de arquivos (fora do criterio c) |
| `test/api/file-upload.test.ts` | 124 | POST zip file with directory traversal payload | SINALIZADO: zip com traversal devolve 204, mas uma implementacao segura tambem pode devolver 204 |
| `test/api/b2b-order.test.ts` | 37 | POST busy spinning regex attack does not raise an error | SINALIZADO: ReDoS devolve 503; nao afirma sucesso do ataque |
| `test/api/data-export.test.ts` | 52 | Export data with empty JSON body but valid token still succeeds without CAPTCHA | SINALIZADO: exportacao sem CAPTCHA; sem carga de ataque |
| `test/api/data-export.test.ts` | 72 | Export data without use of CAPTCHA | SINALIZADO: exportacao sem CAPTCHA; sem carga de ataque |
| `test/api/b2b-order.test.ts` | 25 | POST endless loop exploit in "orderLinesData" will raise explicit error | defesa: loop infinito detectado (500) |
| `test/api/b2b-order.test.ts` | 48 | POST sandbox breakout attack in "orderLinesData" will raise error | defesa: sandbox breakout gera erro (500) |
| `test/api/challenge.test.ts` | 96 | PUT invalid continue code is rejected (non-alphanumeric) | defesa: carga XSS rejeitada (404) |
| `test/api/feedback.test.ts` | 32 | POST sanitizes unsafe HTML from comment | defesa: HTML inseguro removido |
| `test/api/file-serving.test.ts` | 52 | GET a restricted file directly from file system path on server via URL-encoded Directory Traversal attack loads index.html instead | carga de traversal sem efeito: devolve index.html |
| `test/api/file-serving.test.ts` | 155 | GET a key file whose name contains a "/" fails with a 403 error | defesa: barra no nome rejeitada (403) |
| `test/api/file-upload.test.ts` | 64 | POST file type XML with XXE attack against Windows | XXE: upload XML descontinuado (410) |
| `test/api/file-upload.test.ts` | 72 | POST file type XML with XXE attack against Linux | XXE: upload XML descontinuado (410) |
| `test/api/file-upload.test.ts` | 80 | POST file type XML with Billion Laughs attack is caught by parser | defesa: Billion Laughs detectado pelo parser |
| `test/api/ftp-folder.test.ts` | 163 | GET a file whose name contains a "/" fails with a 403 error | defesa: barra no nome rejeitada (403) |
| `test/api/login.test.ts` | 225 | POST login with query-breaking SQL Injection attack | defesa: SQL que quebra a consulta devolve 401 |
| `test/api/quarantine-server.test.ts` | 27 | GET responds with 403 when filename contains a forward slash | defesa: barra no nome rejeitada (403) |
| `test/api/search.test.ts` | 153 | GET product search by description cannot select logically deleted christmas special due to forced early where-clause termination | carga sem efeito: produto excluido nao aparece |
| `test/api/security-question.test.ts` | 100 | GET security question is not susceptible to SQL Injection attacks | defesa: nao suscetivel a SQL injection |
| `test/api/user-profile.test.ts` | 82 | GET user profile falls back gracefully when SSTI payload throws | vale com ou sem a falha: nome exibido literalmente |
| `test/server/insecurity.unit.test.ts` | 131 | removes all Javascript from HTML input | defesa: sanitizacao remove scripts |
| `test/server/insecurity.unit.test.ts` | 180 | removes all Javascript from HTML input | defesa: sanitizacao segura remove scripts |
| `test/server/insecurity.unit.test.ts` | 186 | cannot be bypassed by exploiting lack of recursive sanitization | defesa: sanitizacao segura nao e contornada |
| `test/server/xml.unit.test.ts` | 34 | should timeout on entity expansion bomb | defesa: bomba de entidades interrompida |
| `test/server/fileServer.unit.test.ts` | 27 | should serve PDF files from folder /ftp | mock do caminho de chamada (sendFile): F por definicao |
| `test/server/fileServer.unit.test.ts` | 36 | should serve Markdown files from folder /ftp | mock do caminho de chamada (sendFile): F por definicao |
| `test/server/fileServer.unit.test.ts` | 45 | should serve incident-support.kdbx files from folder /ftp | mock do caminho de chamada (sendFile): F por definicao |
| `test/server/keyServer.unit.test.ts` | 21 | should serve requested file from folder /encryptionkeys | mock do caminho de chamada (sendFile): F por definicao |
