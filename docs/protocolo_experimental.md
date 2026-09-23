# Protocolo experimental

## 1. Alvo

| Item | Valor |
|---|---|
| Projeto | OWASP Juice Shop |
| Versão | v20.1.1 |
| Commit fixado | `8ff89794d2188005e23ed0649aadb7b6faae1b36` |
| Node.js exigido (`engines`) | `22 - 26` |
| Node.js confirmado no ambiente | **pendente** — `node --version` nunca retornou com sucesso nas tentativas registradas no caderno; confirmar antes de fechar esta seção |
| npm | `11.19.0` |
| Python | `3.11.16` |
| git | `2.50.1` |

## 2. Ferramenta SAST e versionamento

| Item | Valor |
|---|---|
| Ferramenta | Semgrep |
| Versão | `1.177.0` — registrada em toda execução (Decisão D2) |
| Rulesets | `p/javascript`, `p/typescript`, `p/nodejs`, `p/expressjs`, `p/owasp-top-ten` |
| Flags fixas | `--json --no-git-ignore --metrics=off` |
| Worktree de referência | `workspace/wt-1` |

**Risco de não-versionamento conhecido e aceito (D2):** os rulesets do registro não são versionados — podem mudar sem aviso entre execuções em datas diferentes. Mitigação: a versão do Semgrep é registrada em toda execução e o JSON bruto (`outputs/sast_antes/baseline_raw.json`) é arquivado como fonte primária.

**Achado adicional (F3.2, registrado no caderno):** o Semgrep aplica uma lista de exclusão padrão embutida no próprio binário (reportada como `.semgrepignore patterns`, 1444 arquivos na execução de referência) mesmo sem nenhum `.semgrepignore` explícito no projeto. Essa lista não é controlada por `config/semgrepignore` e está sujeita ao mesmo risco de mudança entre versões.

## 3. Protocolo de filtragem (determinístico, aplicado antes de qualquer chamada à LLM)

1. **Excluir caminhos** — `config/semgrepignore`, convertido em flags `--exclude` (uma por linha, não existe flag de arquivo único — ver caderno, entrada de 2026-09-24):
   ```
   node_modules/, build/, dist/, frontend/dist/, frontend/node_modules/,
   coverage/, test/, data/static/codefixes/, vagrant/, screenshots/,
   logs/, frontend/src/assets/private/three.js, .github/, .npmrc,
   *.min.js, *.map
   ```
   `data/static/codefixes/` é excluído especificamente como mitigação de contaminação de treinamento (Parte 0, Risco 3). `logs/` e `three.js` foram adicionados após identificar, na execução de referência, que eram respectivamente um artefato de runtime e uma biblioteca de terceiros vendorizada — nenhum dos dois é código-fonte da aplicação. `.github/` e `.npmrc` foram adicionados após a execução de F3.6 revelar que 9 dos 21 findings elegíveis (43%) caíam em workflows de CI/CD e configuração do npm — a mesma fronteira de escopo do Adendo M1 (vulnerabilidades de supply chain/dependências fora do escopo), só identificada mais tarde porque os rulesets usados cobrem YAML incidentalmente. Nenhum dos dois é testável pela suíte automatizada do Juice Shop.

2. **Manter apenas findings de `metadata.category == "security"`.**

3. **Manter apenas os dois níveis mais críticos de severidade**, cobrindo os dois esquemas do Semgrep que coexistem na mesma execução (achado do caderno, entrada de 2026-09-25): `ERROR`/`WARNING` (esquema legado) e seus equivalentes `HIGH`/`MEDIUM`/`CRITICAL` (esquema atual de 4 níveis). Exclui-se apenas o nível mais baixo em qualquer um dos dois (`INFO`/`LOW`).

4. **Manter apenas findings com CWE mapeada** em `metadata.cwe`.

5. **Deduplicar por `(check_id, path)`** — mesma regra no mesmo arquivo conta uma vez.

6. **Amostragem estratificada por categoria OWASP** (não acionada nesta execução — 21 findings elegíveis, bem abaixo de qualquer `N_max` calculado em F2.4).

### Resultado da execução de referência

> **Nota de reconciliação.** A primeira exclusão de `.github/`/`.npmrc` derrubou os findings brutos de 30 para 15 (queda de 15, não os 9 esperados pela contagem pós-dedupe da execução anterior). Reconciliado: dos 30 brutos originais, 15 já eram código de aplicação (idênticos aos 15 desta execução) e 15 eram de `.github/`/`.npmrc`, dos quais só 9 sobreviviam à deduplicação (6 eram duplicatas internas, mesma regra disparando mais de uma vez no mesmo arquivo de workflow). As siglas `CMDI` e `INTEGRITY` desapareceram por completo da lista final — 100% dos achados dessas duas categorias estavam em configuração de CI/CD, nenhum na aplicação.

| Etapa | Contagem |
|---|---|
| Findings brutos (após exclusão de caminhos, incl. `.github/`/`.npmrc`) | 15 |
| Duplicatas removidas (passo 5) | 3 |
| Após deduplicação | 12 |
| Elegíveis após filtragem completa (passos 2–4) | 12 |
| Excluídos | 0 |
| Fora do código de aplicação | 0 |
| Com marcador `vuln-code-snippet` (ground truth parcial) | 5 de 12 |

## 4. Taxonomias e mapeamentos

### 4.1 CWE → sigla de vulnerabilidade (`config/mapa_cwe_vuln.yaml`)

Doze siglas definidas a priori (Decisão D7, a partir do referencial teórico do TCC 1), mais sete adicionadas após rodar o baseline real e encontrar CWEs não previstas (caderno, entrada de 2026-09-25: `CWE-95`, `CWE-73`, `CWE-1357`, `CWE-353`, `CWE-829`, `CWE-601`, `CWE-548`). Duas das adições reaproveitam siglas existentes (mesma família); três (`CWE-1357`, `CWE-353`, `CWE-829`) formaram uma sigla nova, `INTEGRITY`, sem documento de RAG correspondente ainda — ver Seção 4.3.

### 4.2 OWASP 2021 → OWASP 2025 (`config/mapa_owasp.yaml`)

O Semgrep rotula findings na numeração OWASP 2021; o referencial teórico do TCC usa a numeração 2025. Tabela de conversão confirmada contra a publicação oficial (`https://top10.owasp.org/2025/`):

| 2021 | 2025 | Observação |
|---|---|---|
| A01 Broken Access Control | A01 | Absorve SSRF (A10:2021) |
| A02 Cryptographic Failures | A04 | |
| A03 Injection | A05 | |
| A04 Insecure Design | A06 | |
| A05 Security Misconfiguration | A02 | |
| A06 Vulnerable and Outdated Components | A03 | Renomeada: Software Supply Chain Failures |
| A07 Identification and Authentication Failures | A07 | Renomeada: Authentication Failures |
| A08 Software and Data Integrity Failures | A08 | |
| A09 Security Logging and Monitoring Failures | A09 | Renomeada: Security Logging and Alerting Failures |
| A10 Server-Side Request Forgery | A01 | Absorvida por Broken Access Control |
| — | A10 | Categoria nova: Mishandling of Exceptional Conditions (sem equivalente 2021) |

### 4.3 Sigla → categoria de RAG (`config/mapa_categoria_rag.yaml`)

**Marcado como proposta, não decisão fechada** (o próprio arquivo YAML declara isso no cabeçalho). Mapeia cada sigla de vulnerabilidade a um dos 7 documentos previstos em `knowledge_base/` (F1.3). Pendência conhecida: a sigla `INTEGRITY` (5 dos 21 findings elegíveis da execução de referência, ~24%) não tem documento correspondente entre os 7 previstos — decisão em aberto entre criar um 8º documento (`integrity_failures.md`) ou tratar essas issues como "sem RAG" nas estratégias P3/P4. Revisar quando os documentos da base de conhecimento forem escritos (F5).

## 5. Ground truth parcial (F3.5)

Findings cuja faixa de linhas cai dentro de um bloco `// vuln-code-snippet start/end <desafio>` do próprio Juice Shop são marcados com o nome do desafio em `marcador_juiceshop`. Isso não é uma lista exaustiva de vulnerabilidades reais (o Juice Shop tem falhas não demarcadas), mas todo marcador presente confirma uma vulnerabilidade intencional conhecida — usado na análise de resultados para distinguir findings sobre vulnerabilidades confirmadas de findings incidentais.

## 6. Rastreabilidade

Toda execução do baseline gera: `outputs/sast_antes/baseline_raw.json` (saída bruta do Semgrep, arquivada), `outputs/sast_antes/catalogo_issues.json` (todos os findings, elegíveis e excluídos, com motivo), `outputs/sast_antes/relatorio_baseline.md` (agregações para o caderno). O commit do alvo, a versão do Semgrep e os rulesets usados ficam registrados nesta seção do protocolo, não apenas no código.