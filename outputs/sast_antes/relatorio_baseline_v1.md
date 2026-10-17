# Relatorio do baseline SAST

- Findings brutos (Semgrep, apos exclusao de caminhos em D1): 15
- Duplicatas removidas (mesma regra + arquivo): 3
- Total apos deduplicacao: 12
- Elegiveis apos protocolo de filtragem (D1): 12
- Excluidos: 0
- Elegiveis com marcador vuln-code-snippet (ground truth parcial, F3.5): 5 de 12
- **Fora do codigo de aplicacao (CI/CD, .npmrc etc. -- revisar escopo, ver caderno): 0 de 12**

## Por severidade (bruta, como reportada pelo Semgrep)

- WARNING: 7
- ERROR: 5

## Por severidade (normalizada -- ALTA = ERROR/HIGH/CRITICAL, MEDIA = WARNING/MEDIUM)

- MEDIA: 7
- ALTA: 5

## Por CWE (primeira CWE de cada finding -- ver nota na funcao cwe_codigo)

- CWE-73: 4
- CWE-89: 4
- CWE-798: 1
- CWE-601: 1
- CWE-95: 1
- CWE-548: 1

## Por sigla de vulnerabilidade

- PATHTRAV: 4
- SQLI: 4
- HARDCRED: 1
- OPENREDIR: 1
- CODEINJ: 1
- INFOEXPOSURE: 1

## Por categoria OWASP 2025

- A05: 5
- A06: 4
- A01: 2
- A07: 1

## Top 10 arquivos com mais findings

- routes/login.ts: 2
- routes/search.ts: 2
- lib/insecurity.ts: 1
- routes/fileServer.ts: 1
- routes/keyServer.ts: 1
- routes/logfileServer.ts: 1
- routes/quarantineServer.ts: 1
- routes/redirect.ts: 1
- routes/userProfile.ts: 1
- server.ts: 1
