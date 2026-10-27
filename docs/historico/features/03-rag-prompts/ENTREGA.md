# Entrega da feature 03 — RAG e prompts P3/P4

**Data:** 13/10/2026.  
**Status:** implementada e validada sem API, com limites documentados.  
**Publicação:** somente alterações locais; sem commit ou push.

## Resultado verificado

- 10 documentos PRONTO e manifesto 1.0 publicados e validados por leitura.
- 115 testes unitários passaram (94 anteriores + 21 novos), sem skips nesta validação.
- 312 prompts para 78 casos × P1/P2/P3/P4; 156 recuperações RAG.
- 234 referências P1/P2/P1L e 156 prompts da feature 02 mantiveram mensagens e hashes.
- 559 arquivos históricos em outputs/config/rules conservaram os hashes.
- Contrato 2.0 e proteção de retomada implementados; contrato antigo comprovado em cópia temporária (161 arquivos idênticos, 156 prompts, 11,394 s).
- Zero chamadas à LLM, custo US$ 0, sem patches ou testes funcionais; worktrees limpas.

## Ambiente e comandos

Python 3.12.3, PyYAML 6.0.3, Semgrep 1.177.0 no ambiente `.venv`. As dependências já preparadas da feature 02 foram reutilizadas; não houve instalação nesta entrega.

Commit dos checkouts `workspace/wt-1` e `workspace/catalogo-alvo`: `f915bddd82790d0f3018902d36ae9b4241a5f51f`.

```bash
.venv/bin/python scripts/experiment/validate_knowledge_base.py --publicar-manifesto
.venv/bin/python scripts/experiment/validate_knowledge_base.py
make test-unit PYTHON=.venv/bin/python
PYTHONPATH=src .venv/bin/python -m pipeline.run_pipeline \
  --execucao AMP_RAG_PREFLIGHT_01 \
  --catalogo outputs/catalogos/ampliado_v1/catalogo_issues.json \
  --perfil-sast config/perfis/ampliado_v1/perfil.json \
  --saida outputs/feature03/AMP_RAG_PREFLIGHT_01 \
  --estrategias P1,P2,P3,P4 --somente-preflight --k 1 \
  --semgrep-bin .venv/bin/semgrep
git diff --check
```

Publicação do manifesto foi feita uma vez, após autoria/revisão dos dez documentos; recusa uma segunda publicação. O preflight reusa baseline verificado ao retomar. O comando de publicação não deve ser usado para sobrescrever a versão entregue.

## Cobertura medida

| Categoria recuperada | Casos | Recuperações P3/P4 |
|---|---:|---:|
| authentication_failures | 3 | 6 |
| broken_access_control | 25 | 50 |
| concurrency | 1 | 2 |
| cross_site_scripting | 12 | 24 |
| cryptographic_failures | 9 | 18 |
| generico | 0 | 0 |
| injection | 12 | 24 |
| input_validation | 5 | 10 |
| integrity_failures | 1 | 2 |
| security_misconfiguration | 10 | 20 |
| **Total** | **78** | **156** |

Todos os casos foram selecionados por CWE, sem fallback no catálogo oficial. Os 32 casos originalmente `generico` conservaram essa categoria no catálogo e receberam documentos pelas associações complementares do índice novo. Foram mantidos 21 falsos positivos e 49 casos sem OWASP. Não existem casos com múltiplas CWEs nesse catálogo; ordem da primeira CWE mapeada e fallback foram verificados com fixtures sintéticas.

Corpos entre 1.742 e 2.278 caracteres. Tamanhos totais das mensagens P3: 4.439–13.711 caracteres; P4: 4.900–14.172. Medianas: 7.430,5 e 7.891,5. São caracteres, não tokens; custo/tokens do piloto ainda não foram medidos.

## Inspeção das amostras

Foram conferidos o alerta, a ordem dos blocos, o corpo recuperado e a ausência do frontmatter em P3/P4 para uma amostra de cada categoria efetiva. IDs são registrados apenas neste relatório, não na base documental.

| Categoria | Caso inspecionado | Observação |
|---|---|---|
| cryptographic_failures | `AMPfd83fe121712cbab` | Falso positivo em Gruntfile; documento distingue hash de senha de uso não secreto; OWASP ausente. |
| cross_site_scripting | `AMP746c0b4d1a2f8ed4` | Bypass Angular; documento exige investigar origem e contexto de renderização. |
| broken_access_control | `AMPd53a8fdb9fb5d682` | CWE-915/poluição de protótipo: contexto amplo de propriedades; não fornece orientação específica para esse mecanismo. |
| security_misconfiguration | `AMP15048bdd08a98d80` | ReDoS; recomenda avaliar entrada/tamanho e alcance antes de alterar. |
| integrity_failures | `AMP38978d46852a6db3` | Codificação Z85 não é prova de autenticidade; contexto distingue formato de origem. |
| injection | `AMPf7a5e2edd454d398` | XML/XXE; documento separa parser XML de parametrização SQL. |
| input_validation | `AMPff4689848e9b84b8` | Faixa de rating; documento separa tipo de invariante. |
| authentication_failures | `AMP9ea0dd6316734fd8` | Mudança de senha; documento distingue reautenticação de recuperação. |
| concurrency | `AMP5c9cd865e297e422` | Contador/elegibilidade; documento exige atomicidade real do armazenamento. |

O documento genérico foi inspecionado pela fixture sem CWE/categoria, e a ordem de CWEs pela fixture `CWE-999999, CWE-362, CWE-79`, que selecionou CWE-362. Os documentos foram escritos sem consultar codefixes ou incorporar trechos do alvo. Exemplos de APIs abstratas explicitam suposições e necessidade de adaptação/verificação.

## Hashes e evidências

| Artefato | SHA-256 |
|---|---|
| Manifesto / base | `cf045f301150dcee988daeb0f3bea488073f477f096d656f8b7c1dce7dfe1638` |
| Índice | `8a7f99607a952027759dd6497fc9843e1e6ae515c1970523aeb50e82c44ce24c` |
| Contrato 2.0 | `f0665fea5058e01dd5c98e8e909d7456b64d6c60efcc43fac5819e3b2d60f8f7` |
| Preflight | `d3001f6393b28830eabcfefb91316bc12ebfda3c34976a950eb8f11d8c11d916` |

| Documento 1.0 | Arquivo completo | Corpo |
|---|---|---|
| authentication_failures | `e85e6494b059648fb64047c614a374c9eefc9799f94839b221ff6a5c6d7a74b1` | `bbff9d523a8216b648b28220b7f869e0af97f708953abf043029aa0f95d74975` |
| broken_access_control | `a875510e9f2f9968ace038660383e29d0671146096d7af5e47bcf3057229eeac` | `5f5d76b7563a7175d29c19a5a3b563e65a0a66789f298b0abc806c9028048e36` |
| concurrency | `9275fcb4360ff21b77a8bccff8682b000b5844f725a4afad0f234a52312da591` | `116472b76a8616ef3391d438b03c737b8f3b8d643c68a148760210e49ce896b1` |
| cross_site_scripting | `e715ede7f87b4c855fd406402fafcd692e13fae8f4c3e5ee97748522aa9cb705` | `2e5b8916145727d787f80997248aa54de25da3d97605739a9b8919ac419c4282` |
| cryptographic_failures | `7758086bcd6963dce25d419c76df27abe7844b4da9100192cc387d8e351af3f1` | `ecd95164abb6c0fbf95fdc3bdca9369ccf1293a3ee51de37448fa05e9906797b` |
| generico | `d2d5e72e6aa1111d68f39da6fe63d1c78a36cdd62d14013d8c3dd8724888a23e` | `0061e6c5b789df686e5963a14fd43e3f693810c2865975c5d8b89286805e211c` |
| injection | `2f8bcf8a479c27fdf7b365799dda06d8d27acde4af36714d235a6c3b5b63111b` | `ce74cbafdb6f9fcaa06ced46218a0acce20f4ee7bdfb332130debcc39a97b896` |
| input_validation | `a02b8c1d0f81945731e606599f917e48c1f26273b679cc75b1203962a56feed5` | `69e0f8bbcf5eb036118db9de3e10b4394418c3873fa25f321dbefce900331a54` |
| integrity_failures | `36e31934b593726242fdae50053a811dab86b935fdff1a46b3959b9fe9ef1ae6` | `82f7f96acfdca4fba8138d2df4c412307be785bcb933489c0bc2927e46c79594` |
| security_misconfiguration | `5ed2f0943efd00af57954da47c9535b817b2fd1c99438e2d6beb15806229600a` | `024d0de3e4e6b244881c185d73ff286f57dcad436a6104dfbc639d9e85fa8dd9` |

- [Manifesto publicado](../../../../knowledge_base/manifesto.json).
- [Preflight e metadados](../../../../outputs/feature03/AMP_RAG_PREFLIGHT_01/preflight.json).
- [Gate de reprodução](../../../../outputs/feature03/AMP_RAG_PREFLIGHT_01/sast_antes/reproducao.json): 78/78, sem ausentes/adicionais; oito diagnósticos preexistentes.
- [Cobertura e amostras](../../../../outputs/feature03/cobertura_rag.json).
- [Fallback sintético](../../../../outputs/feature03/fallback_sintetico.json) e [múltiplas CWEs](../../../../outputs/feature03/multiplas_cwes_sintetico.json).
- [Compatibilidade antiga](../../../../outputs/feature03/compatibilidade_antiga.json), exercitada sem alterar a feature 02.
- [Validação final e retomada 2.0](../../../../outputs/feature03/validacao_final.json).
- [Verificação da entrega](../../../../outputs/feature03/verificacao_entrega.json) e [hashes históricos capturados](../../../../outputs/feature03/preparacao/artefatos_historicos_sha256.json).
- [Referências textuais anteriores](../../../../outputs/feature03/preparacao/referencia_prompts_semrag.json) e [builder antes da alteração](../../../../outputs/feature03/preparacao/builder_anterior.py.txt).

## Fontes consultadas

Páginas primárias verificadas durante a autoria em 13/10/2026. Título, URL e data constam no frontmatter e no manifesto; testes automatizados não consultam a web. Textos e exemplos são originais, sem transcrição extensa.
- [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).
- [Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
- [Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).
- [CWE-22: Path Traversal](https://cwe.mitre.org/data/definitions/22.html).
- [Server Side Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
- [Unvalidated Redirects and Forwards Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html).
- [CWE-362: Race Condition](https://cwe.mitre.org/data/definitions/362.html).
- [Sequelize v6: Transactions](https://sequelize.org/docs/v6/other-topics/transactions/).
- [Cross Site Scripting Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html).
- [Angular: Security](https://angular.dev/best-practices/security).
- [Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html).
- [Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).
- [Secure Code Review Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html).
- [Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html).
- [SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).
- [NoSQL Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/NoSQL_Security_Cheat_Sheet.html).
- [XML External Entity Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html).
- [Node.js: VM](https://nodejs.org/api/vm.html).
- [CWE-20: Improper Input Validation](https://cwe.mitre.org/data/definitions/20.html).
- [CWE-345: Insufficient Verification of Data Authenticity](https://cwe.mitre.org/data/definitions/345.html).
- [CWE-200: Exposure of Sensitive Information](https://cwe.mitre.org/data/definitions/200.html).
- [Denial of Service Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html).

## Limitações e próximo passo

O contexto por categoria pode ser amplo: CWE-915 não possui seção específica de poluição de protótipo nesta versão, e exemplos criptográficos exigem distinguir uso secreto de hash não secreto. Não houve adaptação dos documentos aos resultados de remediação. Mudanças futuras exigem nova versão documental e nova saída RAG, preservando esta evidência.

Gerar prompts não confirma vulnerabilidades ou eficácia de correções. P3/P4 combinam alerta SAST e documentação; não permitem atribuir um efeito apenas ao RAG. Os oito diagnósticos de parsing e os limites funcionais do servidor da feature 02 continuam aplicáveis. F e resultados históricos não foram alterados.

Próxima entrega: definir piloto contrastante com orçamento e parâmetros congelados, executar correções reais e revisar R/F/M, incluindo testes dependentes de linha e delimitação da cobertura de frontend. Nenhum piloto com API foi iniciado aqui.
