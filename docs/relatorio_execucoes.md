# Resumo das execuções (E01, E02, E03)

Gerado em 2026-10-17 por `scripts/relatorio_execucoes.py`, só a partir dos arquivos em `outputs/`. Modelo `gpt-4.1-mini`, Semgrep 1.177.0 sem login, Juice Shop v20.1.1 (`f915bdd`).

## Issues (alertas do Semgrep)

| Catálogo | Rulesets | Brutos | Elegíveis | Locais distintos | Com `vuln-code-snippet` |
|---|---:|---:|---:|---:|---:|
| v1 (E01, E02) | 5 | 15 | 12 | 10 | 5 |
| v2 (E03) | 11 | 28 | 22 | 18 | 5 |

- Triagem manual do v2: 15 confirmados, 6 falsos positivos, 1 inconclusivo, 0 não triados (nenhum é excluído).
- Siglas do v2: XSS 5, PATHTRAV 4, SQLI 4, CODEINJ 3, HARDCRED 2, OPENREDIR 2, CREDPROT 1, INFOEXPOSURE 1.
- OWASP 2025 do v2: A01 3, A05 12, A06 5, A07 2.
- Sondagem, exclusões antigas: 5 rulesets 15 brutos / 12 elegíveis; 11 rulesets 35 / 27. Com login (13/10, não adotado): 37 brutos / 29 elegíveis.

## Prompts, chamadas e custo

| Execução | Catálogo | Casos | Tentativas | Por estratégia | Chamadas pagas | Do cache | Tokens (entrada + saída) | Custo |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| E01 | v1 | 12 | 24 | P1 12, P2 12 | 19 | 5 | 27.017 + 9.220 | US$ 0,0250 |
| E02 | v1 | 12 | 36 | P1 12, P1L 12, P2 12 | 12 | 24 | 17.887 + 6.684 | US$ 0,0178 |
| E03 | v2 | 22 | 66 | P1 22, P1L 22, P2 22 | 24 | 42 | 37.075 + 16.296 | US$ 0,0398 |

Chamada do cache: prompt idêntico a uma chamada anterior; não é cobrada de novo (D8).

## Tempo

| Execução | Duração da sessão | Tentativa aplicada: média | LLM | SAST depois | Validação |
|---|---:|---:|---:|---:|---:|
| E01 | 7 min 31 s (1 sessão, K = 4) | 1 min 15 s | 5 s | 5 s | 1 min 05 s |
| E02 | 17 min 30 s (1 sessão, K = 4) | 2 min 01 s | 5 s | 4 s | 1 min 52 s |
| E03 | 59 min 58 s (1 sessão, K = 4) | 3 min 57 s | 5 s | 7 s | 3 min 46 s |

A duração da sessão é o tempo de processamento (depois da checagem de ambiente) com K cópias em paralelo; os tempos por tentativa somam as camadas de uma tentativa aplicada.

## Correções aceitas (R = F = M = 1)

Leitura (a): cada estratégia sobre todos os casos. Leitura (b): cadeia P1 → P2 do TCC 1, por caso. Os números são casos aceitos sobre o total de casos; P1L é diagnóstico, fora da cadeia.

### E01

| Definição de F | P1 (a) | P2 (a) | Cadeia (b) | P1L | TRV da cadeia |
|---|---:|---:|---:|---:|---:|
| sem separação | 0/12 | 0/12 | 0/12 | - | 0,000 |
| d_marcador | 0/12 | 0/12 | 0/12 | - | 0,000 |
| d_criterio | 3/12 | 2/12 | 3/12 | - | 0,143 |
| d_criterio_amplo | 3/12 | 2/12 | 3/12 | - | 0,143 |

- Casos aceitos (`d_criterio`, cadeia): JS005, JS006, JS011.
- Por triagem manual (`d_criterio`, cadeia): confirmado 3/11; inconclusivo 0/1.
- Não aplicadas: 2 (ancora_nao_encontrada 2). Rejeitadas (`d_criterio`): R0F1M1 10, R1F0M1 9, R0F0M1 3.

### E02

| Definição de F | P1 (a) | P2 (a) | Cadeia (b) | P1L | TRV da cadeia |
|---|---:|---:|---:|---:|---:|
| sem separação | 0/12 | 0/12 | 0/12 | 1/12 | 0,000 |
| d_marcador | 0/12 | 0/12 | 0/12 | 1/12 | 0,000 |
| d_criterio | 3/12 | 2/12 | 3/12 | 2/12 | 0,143 |
| d_criterio_amplo | 3/12 | 2/12 | 3/12 | 3/12 | 0,143 |

- Casos aceitos (`d_criterio`, cadeia): JS005, JS006, JS011.
- Por triagem manual (`d_criterio`, cadeia): confirmado 3/11; inconclusivo 0/1.
- Não aplicadas: 3 (ancora_nao_encontrada 3). Rejeitadas (`d_criterio`): R0F1M1 14, R1F0M1 7, R0F0M1 5.

### E03

| Definição de F | P1 (a) | P2 (a) | Cadeia (b) | P1L | TRV da cadeia |
|---|---:|---:|---:|---:|---:|
| sem separação | 3/22 | 2/22 | 3/22 | 5/22 | 0,073 |
| d_marcador | 3/22 | 2/22 | 3/22 | 5/22 | 0,073 |
| d_criterio | 7/22 | 4/22 | 7/22 | 7/22 | 0,189 |
| d_criterio_amplo | 7/22 | 4/22 | 7/22 | 8/22 | 0,189 |

- Casos aceitos (`d_criterio`, cadeia): JS005, JS006, JS011, JS013, JS014, JS016, JS019.
- Por triagem manual (`d_criterio`, cadeia): confirmado 4/15; falso_positivo 3/6; inconclusivo 0/1.
- Não aplicadas: 9 (ancora_nao_encontrada 9). Rejeitadas (`d_criterio`): R0F1M1 21, R0F0M1 10, R1F0M1 7, R1F1M0 1.


## Observações (escritas à mão; os números acima são gerados)

- **Falsos positivos "corrigidos".** Na E03, 3 dos 6 casos julgados falsos positivos foram aceitos (JS013, JS014, JS016): o alerta sumiu e os testes passaram, mas não havia vulnerabilidade. Entre os 15 confirmados, 4 foram aceitos (JS005, JS006, JS011, JS019). A TRV inclui os dois grupos; a separação está na linha "Por triagem manual".
- **O M pegou uma regressão.** Em JS021/P1 (falso positivo em `views/dataErasureForm.hbs`), a LLM trocou `{{_title_}}` por `{{{_title_}}}`, que desliga o escape do Handlebars. Surgiu o alerta `template-explicit-unescape` e a tentativa foi rejeitada (R1F1M0).
- **Mesmo arquivo, mesmo prompt.** P1 e P2 não informam o alerta, então casos de regras diferentes no mesmo local recebem a mesma resposta (do cache): JS015 = JS001, JS018 = JS008, JS019 = JS011 (no v1, JS005 = JS006 e JS009 = JS010). Só o P1L distingue; ele foi o único a aceitar JS001 e JS021.
- **Não aplicadas:** 9 na E03, todas por âncora não encontrada (a LLM citou um trecho que não existe no arquivo), em JS011, JS012, JS017, JS019 e JS022.
- **Tempo.** A E03 levou 60 min (mais 7 min de checagem de ambiente), contra 17,5 min da E02: são 66 tentativas contra 36, e o T4 ficou mais lento (média de 76 s contra 41 s, 26 reexecuções contra 14). O T4 roda uma cópia por vez.
- **Ressalvas.** P3 e P4 (RAG) ainda não rodaram. Os 12 casos do v1 reaproveitam as respostas da E02 (cache), mas R e M foram medidos de novo com os 11 rulesets.
