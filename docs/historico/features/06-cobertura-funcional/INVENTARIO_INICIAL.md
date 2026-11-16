# Inventário inicial — feature 06

**Data:** 17/10/2026.  
**Natureza:** conferência por leitura; não é revisão da adequação nem execução de testes.

Fonte: [catálogo ampliado](../../../../outputs/catalogos/ampliado_v1/catalogo_issues.json) e
[mapa atual](../../../../config/mapa_testes_relacionados.yaml).

- 78 casos em 46 arquivos; o mapa contém os mesmos 46 caminhos.
- Dois arquivos e dois casos têm seleção relacionada; 44 arquivos e 76 casos usam fallback amplo.
- Há 13 casos em 11 arquivos frontend; três desses casos estão em dois arquivos `.spec.ts`.
- Todos os casos precisam de revisão de adequação nesta feature, inclusive login/keyServer.

O modo `amplo` não prova que as suítes amplas cobrem a funcionalidade. Na política
`relacionada_v1`, ele impede a preparação do caso; não aciona a suíte inteira.
A existência de testes relacionados também não prova que suas asserções bastam.

| Arquivo | Casos | Seleção atual | Adequação nesta feature |
|---|---:|---|---|
| `Gruntfile.js` | 1 | Fallback amplo | A revisar |
| `data/static/users.yml` | 1 | Fallback amplo | A revisar |
| `frontend/src/app/about/about.component.ts` | 1 | Fallback amplo | A revisar |
| `frontend/src/app/administration/administration.component.ts` | 2 | Fallback amplo | A revisar |
| `frontend/src/app/app.guard.spec.ts` | 1 | Fallback amplo | A revisar |
| `frontend/src/app/data-export/data-export.component.ts` | 1 | Fallback amplo | A revisar |
| `frontend/src/app/last-login-ip/last-login-ip.component.spec.ts` | 2 | Fallback amplo | A revisar |
| `frontend/src/app/last-login-ip/last-login-ip.component.ts` | 1 | Fallback amplo | A revisar |
| `frontend/src/app/score-board/score-board.component.ts` | 1 | Fallback amplo | A revisar |
| `frontend/src/app/search-result/search-result.component.ts` | 2 | Fallback amplo | A revisar |
| `frontend/src/app/track-result/track-result.component.ts` | 1 | Fallback amplo | A revisar |
| `frontend/src/hacking-instructor/helpers/helpers.ts` | 1 | Fallback amplo | A revisar |
| `lib/codingChallenges.ts` | 2 | Fallback amplo | A revisar |
| `lib/insecurity.ts` | 6 | Fallback amplo | A revisar |
| `lib/xml.ts` | 1 | Fallback amplo | A revisar |
| `models/feedback.ts` | 1 | Fallback amplo | A revisar |
| `routes/b2bOrder.ts` | 1 | Fallback amplo | A revisar |
| `routes/basket.ts` | 1 | Fallback amplo | A revisar |
| `routes/basketItems.ts` | 3 | Fallback amplo | A revisar |
| `routes/captcha.ts` | 2 | Fallback amplo | A revisar |
| `routes/changePassword.ts` | 1 | Fallback amplo | A revisar |
| `routes/chat.ts` | 1 | Fallback amplo | A revisar |
| `routes/currentUser.ts` | 2 | Fallback amplo | A revisar |
| `routes/dataErasure.ts` | 2 | Fallback amplo | A revisar |
| `routes/dataExport.ts` | 1 | Fallback amplo | A revisar |
| `routes/delivery.ts` | 1 | Fallback amplo | A revisar |
| `routes/deluxe.ts` | 1 | Fallback amplo | A revisar |
| `routes/fileServer.ts` | 1 | Fallback amplo | A revisar |
| `routes/fileUpload.ts` | 1 | Fallback amplo | A revisar |
| `routes/keyServer.ts` | 1 | Relacionados definidos | A revisar |
| `routes/likeProductReviews.ts` | 3 | Fallback amplo | A revisar |
| `routes/logfileServer.ts` | 1 | Fallback amplo | A revisar |
| `routes/login.ts` | 1 | Relacionados definidos | A revisar |
| `routes/order.ts` | 2 | Fallback amplo | A revisar |
| `routes/orderHistory.ts` | 2 | Fallback amplo | A revisar |
| `routes/profileImageUrlUpload.ts` | 1 | Fallback amplo | A revisar |
| `routes/quarantineServer.ts` | 1 | Fallback amplo | A revisar |
| `routes/redirect.ts` | 1 | Fallback amplo | A revisar |
| `routes/search.ts` | 1 | Fallback amplo | A revisar |
| `routes/showProductReviews.ts` | 1 | Fallback amplo | A revisar |
| `routes/trackOrder.ts` | 1 | Fallback amplo | A revisar |
| `routes/updateProductReviews.ts` | 2 | Fallback amplo | A revisar |
| `routes/userProfile.ts` | 2 | Fallback amplo | A revisar |
| `routes/videoHandler.ts` | 2 | Fallback amplo | A revisar |
| `server.ts` | 12 | Fallback amplo | A revisar |
| `views/promotionVideo.pug` | 1 | Fallback amplo | A revisar |

## Associações específicas existentes

| Fonte | Testes associados no mapa |
|---|---|
| `routes/login.ts` | API: `test/api/login.test.ts`; unitário específico ausente no mapa |
| `routes/keyServer.ts` | Unitário: `test/server/keyServer.unit.test.ts`; API: `test/api/file-serving.test.ts` |

O seletor atual aceita somente `test/server/*.unit.test.ts` e
`test/api/*.test.ts`, incluindo subpastas sob esses prefixos. Testes Angular não
são executáveis por esse contrato. O T0 da raiz exclui `frontend`.

## Identidades da referência

Commit do alvo: `f915bddd82790d0f3018902d36ae9b4241a5f51f`.

Catálogo, SHA-256: `08672899e712fbeef2070f01c58b5867e080e74f716ddc7d8fd10c6d58344aee`.

Mapa atual, SHA-256: `916cf133b19b46646b51533e1fbf63206f090836e8a6e43e8adac87b18ae9954`.

Este inventário permanece como referência inicial. A implementação deverá gerar uma matriz nova com evidências, sem substituir este retrato nem os resultados históricos.
