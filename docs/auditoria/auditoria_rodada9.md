# Rodada 9 — arquivos e autorização

Rodada limitada a `lfrChallenge` e `changeProductChallenge`, ambos incluídos
após revisão e integração local. Nenhuma LLM foi executada, nenhum código
do Juice Shop foi corrigido e nenhuma rodada posterior foi iniciada.

## Resultado acumulado

| Indicador | Rodada 8 | Rodada 9 |
|---|---:|---:|
| Alertas brutos do perfil ampliado | 68 | 72 |
| Confirmados pela revisão | 47 | 49 |
| Falsos positivos | 19 | 21 |
| Inconclusivos | 2 | 2 |
| Desafios distintos confirmados | 41 | 43 |

O perfil ampliado soma `default`, `custom-rules` e rodadas 2–9. A matriz
também conserva scans históricos sobrepostos: suas 103 observações não são
103 vulnerabilidades distintas. Mantém 113 chaves únicas. Os dez candidatos
prioritários originais têm agora seis incluídos: a meta anterior de sete
ainda não foi atingida. Esta execução encerra somente a rodada 9.

## Mecanismos e evidências

### Leitura local por `layout`

Em `routes/dataErasure.ts:103–118`, a rota exige sessão e consulta uma
blacklist de nomes, mas encaminha `...req.body` como opções de `res.render`.
O `path.resolve` usado na verificação não restringe o caminho que hbs usa.
No hbs 4.2.0, `lib/hbs.js` combina `layout` com o diretório de views e lê
o arquivo resultante; caminhos com extensão não precisam ser `.hbs`.

O teste HTTP executa a rota real e hbs real: `layout: '../package.json'`
retorna exatamente os primeiros 100 caracteres do arquivo real, acrescidos
do sufixo da rota. Não foi lido nenhum segredo. O controle que seleciona
somente `email` e `securityAnswer` devolve a página normal, não o arquivo.
Sem sessão a requisição é bloqueada; a blacklist existente ainda bloqueia
um caminho contendo `ftp`. Não se afirma leitura irrestrita de todo arquivo.

O segundo alerta, em `routes/dataErasure.ts:123–126`, foi classificado como
falso positivo para este mecanismo: esse ramo recebe `layout` falsy, não
seleciona o caminho arbitrário demonstrado. Outros possíveis abusos de
opções não foram demonstrados e não são contados.

### Atualização anônima de produto

O alerta em `server.ts:371` é **indireto**: aponta a assimetria entre os
guards de métodos, não a linha comentada nem uma prova automática de falha.
A revisão verifica os middlewares globais, a proteção POST/DELETE, o recurso
Finale criado para Product e seus hooks de tradução/resposta. O recurso
gerado publica PUT sem a proteção equivalente.

O teste HTTP sem cookie/token usa Express, express-jwt, Finale, Sequelize,
SQLite em memória e modelo Product reais. PUT modifica `description` e a
alteração é confirmada por nova leitura do banco. POST e DELETE anônimos
retornam 401. Adicionar o guard real ao PUT, somente no harness protegido,
retorna 401 e impede a persistência da alteração solicitada.

O outro alerta de autorização, em `server.ts:429`, é falso positivo:
`app.use` em 431 protege Quantitys com `isAccounting` e `IpFilter` antes de
Finale. A regra local não reconhece esse controle posterior.

## Regras e tentativa incompleta

As duas regras são genéricas, sem nomes de desafios, caminhos do alvo ou
números de linha. A regra de renderização aponta propagação de opções; a
de autorização é uma heurística de auditoria de baixa confiança, baseada
em DELETE com `denyAll` sem PUT/USE imediatamente anterior. Não é uma
análise completa de autorização e pode perder guards externos ou distantes.
Os fixtures documentam controles externos que ainda geram falsos positivos.
Esses alertas só se tornam confirmados após revisão e testes do mecanismo.

A primeira versão da regra de autorização excedeu 30 segundos em
`server.ts`. Seu [scan incompleto](../../outputs/auditoria_sast/rodada9.json)
e [manifesto](../../outputs/auditoria_sast/manifesto-rodada9.json) permanecem
intactos. A versão inicial da regra está em `rodada9/tentativa_inicial`.
O timeout **não** equivale a ausência de vulnerabilidade ou análise completa.

A revisão substituiu a busca de sequências por todo o escopo por uma
verificação local de guards adjacentes. Isso reduz o custo e a capacidade
de reconhecer proteções; os limites são explícitos, e os dois falsos
positivos não contam para cobertura nem para correção. O timeout permaneceu
em 30 segundos. A matriz utiliza exclusivamente o novo
[scan completo](../../outputs/auditoria_sast/rodada9/scan_completo/rodada9.json),
repetido em `rodada9/repeticao` com os mesmos quatro achados e zero avisos.
Manifestos de ambas as execuções incluem hashes das regras e dos JSONs.

## Testes e limites

- Cinco cenários de integração aprovados (seis entradas TAP com o agrupador).
- 39 testes Python aprovados, incluindo equivalência dos scans, hashes,
  preservação da tentativa incompleta e rejeição de alterações históricas.
- Os 22 conjuntos de exemplos Semgrep passaram, incluindo os dois novos.
- Integração reduzida, não E2E completo: sessão de data erasure, modelo de
  pedido de privacidade e hooks de desafios são simulados. Login, navegador,
  geração de token e o servidor completo não são exercitados. O cenário
  de produtos é anônimo e não depende de token simulado válido.
- Sanitização de descrição é substituída por identidade no teste; usa-se
  texto simples para testar autorização, não XSS. Temas e entidades HTML
  são auxiliares simulados; o motor de leitura/renderização é real.
- Dependências testadas: Express 4.22.1, express-jwt 0.1.3, Finale 1.2.2,
  Sequelize 6.37.3, sqlite3 5.1.7, hbs 4.2.0, Node 24.14.0. O alvo não
  possui lockfile; o ambiente de teste possui lockfile arquivado. Pacotes
  antigos geram avisos de depreciação: são usados somente neste teste local,
  não constituem recomendação para produção.

## Reprodução e artefatos

Alvo limpo no commit `f915bddd82790d0f3018902d36ae9b4241a5f51f`, Semgrep
1.177.0, mesmas exclusões de `config/semgrepignore`. Da raiz do repositório:

```bash
semgrep --test --config rules rules
python3 -m unittest discover -s tests/unit -p 'test_*.py'
python3 scripts/audit/scan_semgrep_exploratorio.py --worktree /caminho/juice-shop --perfis rodada9 --timeout 30 --saida /caminho/novo-scan
npm ci --prefix outputs/auditoria_sast/rodada9/testes/dependencias --no-audit --no-fund
JUICE_SHOP_WORKTREE=/caminho/juice-shop ROUND9_DEPS="$PWD/outputs/auditoria_sast/rodada9/testes/dependencias" node --test tests/integration/rodada9/test.mjs
```

Para arquivar nova evidência, `scripts/audit/verify_rodada9.py` aceita `--worktree`,
`--deps` e `--saida` inexistente. Os testes, lockfile e hashes utilizados
estão em [testes](../../outputs/auditoria_sast/rodada9/testes/manifesto.json).

Reprodução da matriz (Bash; saída nova evita alterar o snapshot):

```bash
audit_args=()
for round in 2 3 4 5 6 7 8 9; do
  scan_path="outputs/auditoria_sast/rodada${round}.json"
  if [ "$round" = 6 ] || [ "$round" = 9 ]; then
    scan_path="outputs/auditoria_sast/rodada${round}/scan_completo/rodada${round}.json"
  fi
  audit_args+=(--scan-extra "rodada${round}=${scan_path}" --triagem-extra "config/auditoria_desafios_rodada${round}.yaml")
done
python3 scripts/audit/build_challenge_matrix.py --worktree /caminho/juice-shop "${audit_args[@]}" --revisoes config/revisoes_associacoes_rodada6.yaml --saida /caminho/nova-matriz
python3 scripts/reports/report_rodada9.py
```

A [matriz CSV](../../outputs/auditoria_sast/rodada9/matriz_desafios.csv), sua
versão JSON, a [comparação](../../outputs/auditoria_sast/rodada9/resumo.json) e
a [triagem](../../config/auditoria_desafios_rodada9.yaml) registram cada alerta.
Não foram alteradas associações históricas, a revisão SSTI, o baseline
JS001–JS012 nem a seleção antiga para correção. A contagem de causas
independentes e uma seleção de correção atualizada continuam pendentes;
dois desafios novos não significam automaticamente duas correções isoladas.
