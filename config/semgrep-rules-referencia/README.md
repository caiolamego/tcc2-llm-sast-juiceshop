# Definições de regras do Semgrep — cópia de referência

**Estas definições são cópia de referência para interpretação dos resultados. Não são as regras que o Semgrep executou na varredura.**

A varredura usa rulesets do registro (`p/javascript`, `p/typescript`, `p/nodejs`, `p/expressjs`, `p/owasp-top-ten` e, desde o catálogo v2, `p/security-audit`, `p/secrets`, `p/xss`, `p/sql-injection`, `p/jwt`, `p/default`), que não são versionados (risco aceito na D2). Execução sempre anônima: com login entram regras proprietárias, que não podem ser copiadas para cá (protocolo, Seção 15). As regras efetivamente executadas na varredura de 2026-09-26, ou em qualquer varredura posterior, **podem divergir** destas cópias.

| Item | Valor |
|---|---|
| Repositório | https://github.com/semgrep/semgrep-rules |
| Ramo | `develop` |
| Commit | `a84ff9cc2453ca91d581380de4b8b3f272f6f4be` (2026-09-22T15:34:05Z) |
| Data da cópia | 2026-10-07 (v1) e 2026-10-13 (v2; baixadas de novo em 2026-10-16) |
| Caminho | igual ao do repositório de origem, a partir de `javascript/` e `generic/` |

São as 14 regras distintas que geram os achados elegíveis dos catálogos: 7 do catálogo v1 (12 casos) e mais 7 do catálogo v2 (22 casos), todas do mesmo commit. Usadas por `scripts/build_issue_catalog.py` para preencher `modo_regra` (`taint` ou `search`) e `saneadores_regra` (padrões de `pattern-sanitizers`), que alimentam a classificação em três faixas do protocolo (Seção 7.3):

1. `search`: casamento de padrão, sem fluxo de dados.
2. `taint` com saneadores declarados.
3. `taint` sem saneadores declarados.

Não editar estes arquivos. Para atualizar, baixar de novo de um commit fixo e registrar o novo commit nesta tabela e no caderno.
