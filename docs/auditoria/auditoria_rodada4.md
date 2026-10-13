# Expansao para desafios sem marcador de trecho vulneravel

Alvo: Juice Shop v20.1.1, commit `f915bddd82790d0f3018902d36ae9b4241a5f51f`;
Semgrep CE `1.177.0` e exclusoes de `config/semgrepignore`. Esta rodada
parte da matriz da rodada 3 e nao altera o baseline JS001-JS012, os scans
anteriores ou resultados da LLM.

## Resultado

| Perfil exploratorio | Alertas brutos | Confirmados | Falsos positivos | Inconclusivos | Desafios distintos confirmados |
|---|---:|---:|---:|---:|---:|
| Acumulado ate a rodada 3 | 45 | 30 | 14 | 1 | 23 |
| Quatro regras novas | 6 | 5 | 1 | 0 | 5 novos |
| Acumulado ate a rodada 4 | **51** | **35** | **15** | **1** | **28** |

As quatro regras genericas em `rules/rodada4/` detectam URL de requisicao
chegando a `fetch`, construcao dinamica de consulta MongoDB `$where`, caminho
de entrada ZIP chegando a escrita em disco e flags de entidades externas no
parser XML. Nenhuma regra contem nome de desafio nem linha do Juice Shop.

| Desafio confirmado | Evidencia alertada | Verificacao manual |
|---|---|---|
| `ssrfChallenge` | `routes/profileImageUrlUpload.ts:24` | `req.body.imageUrl` chega a `fetch(url)` no servidor; autenticacao nao restringe destino. |
| `noSqlCommandChallenge` | `routes/showProductReviews.ts:36` | Quando o desafio esta ativo, ID da rota entra sem conversao numerica no codigo JavaScript de `$where`; teste Cypress usa `sleep(100)`. |
| `noSqlOrdersChallenge` | `routes/trackOrder.ts:18` | ID da rota e interpolado no JavaScript de `$where`; teste Cypress usa expressao sempre verdadeira. |
| `fileWriteChallenge` | `routes/fileUpload.ts:34` | Nome interno do ZIP chega a `createWriteStream`; a verificacao anterior permite sair de `uploads/complaints` e escrever em `ftp/legal.md` dentro do repositorio. |
| `xxeFileDisclosureChallenge` | `lib/xml.ts:35` | `XML_PARSE_NOENT` e `XML_PARSE_DTDLOAD` estao ligados, o provedor de filesystem e registrado e XML enviado pelo usuario chega ao parser. |

O sexto alerta, `routes/chat.ts:149`, e **falso positivo para injeção**:
`id` passa por `Number(id)` antes de entrar no `$where`. O alerta XML foi
associado a `xxeFileDisclosureChallenge`, mas **nao** a `xxeDosChallenge`:
as mesmas flags podem permitir consumo de recursos, porem a existencia e o
impacto de DoS nao foram demonstrados pelo alerta sozinho. Ambos os casos
permanecem visiveis na triagem/matriz, sem inflar a cobertura.

Estes cinco novos vinculos sao `confirmacao_manual_sem_marcador`. A ausencia
de marcador nao foi tratada como confirmacao automatica; cada associacao foi
conferida no fluxo de dados do commit fixado. O total de 82 observacoes na
matriz inclui **todos** os scans arquivados, inclusive perfis sobrepostos;
o perfil acumulado efetivamente discutido nesta secao tem 51 alertas.

## Reproduzir

```bash
semgrep scan --test rules --metrics=off
python3 scripts/audit/scan_semgrep_exploratorio.py \
  --worktree /tmp/tcc-juiceshop-audit --perfis rodada4 \
  --saida "$(mktemp -d /tmp/tcc-semgrep-rodada4-XXXXXX)"
python3 scripts/audit/build_challenge_matrix.py \
  --worktree /tmp/tcc-juiceshop-audit \
  --scan-extra rodada2=outputs/auditoria_sast/rodada2.json \
  --scan-extra rodada3=outputs/auditoria_sast/rodada3.json \
  --scan-extra rodada4=outputs/auditoria_sast/rodada4.json \
  --triagem-extra config/auditoria_desafios_rodada2.yaml \
  --triagem-extra config/auditoria_desafios_rodada3.yaml \
  --triagem-extra config/auditoria_desafios_rodada4.yaml \
  --saida outputs/auditoria_sast/rodada4
python3 scripts/reports/report_rodada4.py
python3 -m unittest discover -s tests/unit -p 'test_*.py'
```

Use Semgrep `1.177.0` (ou passe `--semgrep-bin` ao script). A triagem completa
e o resumo calculado ficam em `outputs/auditoria_sast/rodada4/`. O arquivo
`candidatos_correcao.csv` ainda representa a selecao anterior de 16 causas/20
desafios; nao foi automaticamente ampliado para 28. Antes de uma nova coorte
de correcoes, ainda sera preciso atualizar a selecao, preparar testes de
seguranca e congelar a definicao remota de `p/default`.
