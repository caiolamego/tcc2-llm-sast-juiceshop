# Avaliação das correções de referência do Juice Shop

Data: 17/10/2026. Status: concluída; diagnóstico exploratório, sem mudar o comparador.

## Objetivo e procedimento

Verificar o perfil Semgrep congelado e o comparador `blocos_unicos_v1` antes e
depois das alternativas de correção dos Coding Challenges. Foram usados o commit
`f915bddd82790d0f3018902d36ae9b4241a5f51f`, Semgrep 1.177.0 e
`config/perfis/ampliado_piloto_v1/perfil.json`.

A avaliação é separada do experimento LLM. `codefixes/` continua excluído do scan
do pipeline, dos prompts e do RAG. Nenhuma solução foi incorporada ao catálogo.

Cada referência foi inserida **em uma cópia do arquivo completo original**, no
intervalo delimitado pelos marcadores do desafio. Prefixo, imports e sufixo foram
preservados. Não se fez reparo automático de imports, nomes ou implementação.
A quebra de linha final do trecho foi normalizada. Os trechos substituem também
as linhas ocultas da apresentação pedagógica; portanto essas cópias são fixtures
SAST, não patches funcionais prontos para execução. Isso evita escanear somente
fragmentos incompletos, mas não demonstra compatibilidade de tipos ou execução.

Cada scan usou as regras e exclusões congeladas, IDs sem reescrita, configurações
locais e a mesma versão da ferramenta. Os caminhos relativos originais foram
mantidos dentro de um repositório Git temporário. Os scans anteriores foram
reutilizados somente quando pertenciam ao mesmo arquivo original. Nenhuma
worktree experimental foi alterada, restaurada ou utilizada para executar testes.

**Escopo:** um arquivo completo por fixture. `M_fixture` significa ausência de
novos alertas nesse escopo, e **não M global da aplicação**. F não foi medido.
Não houve execução de LLM, testes funcionais, compilação ou exploração de ataques.

## Cobertura

- 78 casos no catálogo; 47 têm associação com desafios (50 desafios distintos).
- 18 desses desafios têm alternativa com sufixo `_correct`.
- 17 puderam ser montados sem adivinhar limites; `weakPasswordChallenge` ficou
  para revisão manual por usar marcador inline.
- Os 17 desafios cobrem 13 casos distintos dentro dos blocos marcados.
- Foram avaliadas 63 alternativas: 17 marcadas corretas e 46 incorretas.
- Todos os 13 alertas originais avaliados foram reproduzidos. Os 63 pares foram
  analisáveis, sem diagnósticos de parsing nem falha operacional.

Há 17 casos associados a algum desafio com referência correta; quatro ficaram
fora da avaliação automática: MD5/`weakPasswordChallenge`, o handler
`routes/logfileServer.ts` associado à correção de rotas em `server.ts`, a chamada
em `routes/redirect.ts` associada à correção em `lib/insecurity.ts` e o segundo
alerta de métricas fora do bloco corrigido. Associações entre arquivos não foram
transformadas silenciosamente em equivalência de ocorrências.

As várias alternativas do mesmo desafio e os desafios que compartilham o mesmo
caso não são amostras independentes. Os números abaixo não são precisão/recall,
TRV ou resultados de novas gerações LLM. A inspeção deste conjunto é exploratória;
uma avaliação independente futura precisa separar outros arquivos/mecanismos.

## Resultado agregado

| Alternativas | Quantidade | R=1 | R=0 | R indeterminado | M_fixture indeterminado |
|---|---:|---:|---:|---:|---:|
| Marcadas corretas | 17 | 14 | 1 | 2 | 4 |
| Marcadas incorretas | 46 | 20 | 4 | 22 | 24 |

Entre as corretas, 12 tiveram R=1/M_fixture=1; duas tiveram R=1/M_fixture=null;
duas tiveram R=null/M_fixture=null; uma teve R=0/M_fixture=1. As quatro
indeterminações não decorreram de erro do Semgrep.

Das incorretas, 17 também tiveram R=1/M_fixture=1, uma R=1/M_fixture=0 e duas
R=1/M_fixture=null. **Remover o alerta não demonstra que a alternativa é correta**:
a classificação pedagógica inclui falhas funcionais, correções parciais e
mecanismos que a regra pode não modelar. Não se classificou automaticamente
isso como falso negativo sem validar o efeito de segurança da alternativa.

## Referências marcadas corretas

| Desafio | Caso AMP | Alertas da regra antes → depois | R | M_fixture |
|---|---|---:|---:|---:|
| `accessLogDisclosureChallenge` | `AMP44846a9aa9036ad6` | 4 → 3 | ? | ? |
| `changeProductChallenge` | `AMP095fcc0f303ff032` | 2 → 1 | 1 | 1 |
| `dbSchemaChallenge` | `AMP2ab02d839a97d47d` | 1 → 0 | 1 | 1 |
| `directoryListingChallenge` | `AMPee9d50eba0ea870a` | 4 → 3 | ? | ? |
| `exposedMetricsChallenge` | `AMP488a4d26d36eaa6f` | 2 → 1 | 1 | 1 |
| `forgedReviewChallenge` | `AMP4a7e01977b7eba72` | 1 → 0 | 1 | ? |
| `localXssChallenge` | `AMP5bc31b97699a0901` | 2 → 1 | 1 | 1 |
| `loginAdminChallenge` | `AMPfb154534099cb3ca` | 1 → 0 | 1 | 1 |
| `loginBenderChallenge` | `AMPfb154534099cb3ca` | 1 → 0 | 1 | 1 |
| `loginJimChallenge` | `AMPfb154534099cb3ca` | 1 → 0 | 1 | 1 |
| `noSqlReviewsChallenge` | `AMP3d463bdbd0a7b446` | 1 → 0 | 1 | ? |
| `redirectChallenge` | `AMP3378312f4d217863` | 1 → 0 | 1 | 1 |
| `registerAdminChallenge` | `AMP2d60f2c545f1c37a` | 1 → 1 | 0 | 1 |
| `resetPasswordMortyChallenge` | `AMPdab2e8f71cbc8047` | 1 → 0 | 1 | 1 |
| `restfulXssChallenge` | `AMPad5710627036ab1a` | 2 → 1 | 1 | 1 |
| `unionSqlInjectionChallenge` | `AMP2ab02d839a97d47d` | 1 → 0 | 1 | 1 |
| `xssBonusChallenge` | `AMP5bc31b97699a0901` | 2 → 1 | 1 | 1 |

A contagem da regra é do arquivo inteiro: continuar existindo algum alerta dessa
regra não prova que o alvo permaneceu. Por exemplo, remover um de quatro alertas
pode ser uma correção conclusiva, se os três restantes forem associados corretamente.

## Diagnósticos concretos

### 1. Comentários fora do alerta impedem o pareamento

`accessLogDisclosureChallenge` remove a listagem de logs. A chamada de FTP em
`server.ts:269` permanece, com a mesma expressão e coordenadas, mas perde um
comentário de marcador pedagógico. Como o comparador exige igualdade de linhas
inteiras dentro de blocos únicos, ele deixa de parear essa chamada. Sobram dois
alertas anteriores e um posterior no grupo: o alvo removido vira ambíguo junto
com o alerta preservado. A correção de `directoryListingChallenge` reproduz o
problema simétrico: remove FTP e mantém logs, mas R fica indeterminado.

**Mudança indicada:** comparar também o conteúdo exato abrangido pelo finding,
independentemente de comentários fora do seu span, desde que haja correspondência
única e evidência de contexto. Colunas/offsets devem respeitar UTF-8. Não parear
apenas pela posição ou pela contagem quando existirem duplicatas.

### 2. R pode estar resolvido enquanto M continua ambíguo

As correções de `forgedReviewChallenge` e `noSqlReviewsChallenge` removem o alerta
alvo (R=1), mas deixam outro alerta em `routes/updateProductReviews.ts` numa
expressão reescrita. A associação desse outro grupo fica inconclusiva e M_fixture
permanece null. Reprovar automaticamente a correção ou converter M para 1
apagaria uma incerteza real do método.

**Mudança indicada:** uma segunda etapa de pareamento por chamada e escopo,
com contexto estrutural e alinhamento antes/depois. Parear ocorrências preservadas
primeiro, um a um, e manter ambiguidade quando a evidência não distinguir as
ocorrências. Igualdade de regra/arquivo ou uma ocorrência de cada lado não basta.

### 3. Uma correção do desafio pode não resolver o alerta associado

`registerAdminChallenge` fixa o papel `customer`, mas a regra
`tcc.finale.security.generated-default-writes` continua reportando a configuração
genérica de escrita de `finale.resource`. O comparador a identifica corretamente:
R=0/M_fixture=1. O alerta amplo e a atribuição de papel não são a mesma unidade.

**Mudança indicada:** revisar associações desafio–alerta por mecanismo de
vulnerabilidade, não somente sobreposição no bloco. Registrar revisões separadas;
não editar o catálogo congelado nem forçar R=1 porque o nome contém `_correct`.

### 4. Uma alternativa errada pode remover o alerta

No `loginAdminChallenge`, alternativa 3, o SQL fica parametrizado e o alerta some,
mas a senha deixa de ser transformada com `security.hash` antes da comparação.
A própria explicação do desafio informa que isso quebra a autenticação. Remover
o alerta SQL não teria obrigação de detectar esse erro funcional. Já a alternativa
2 também remove o alerta e é marcada como incompleta: a explicação pedagógica e
o mecanismo concreto (que ainda usa hash na senha) precisam de revisão conjunta,
sem tratar a etiqueta como prova automática de exploração.

**Mudança indicada:** manter F e validação de segurança separados de R. Nos testes
de regressão, incluir soluções corretas e incorretas, com expectativa revisada
por alerta e por comportamento. Não ajustar a regra apenas para aprovar o gabarito.

### 5. KeyServer exige avaliação própria

`AMP95adf572d3c6677f` (`routes/keyServer.ts`) não tem desafio associado no catálogo.
As referências avaliadas não constituem gabarito para esse caso. Sua regra continua
reportando o argumento de `res.sendFile`, que foi reescrito nos patches arquivados;
o comparador v1 não associa os spans diferentes. Uma nova associação precisa ser
validada com esses patches e com controles sintéticos, preservando a possibilidade
de R=0 quando o alerta efetivamente persistir. Validar segurança do caminho também
é diferente de resolver exposição pública de chaves, mencionada na auditoria.

## Próximo trabalho recomendado

1. Criar um comparador v2, preservando `blocos_unicos_v1` e os resultados históricos.
   Adicionar pareamento de spans idênticos com unicidade e contexto; depois
   pareamento estrutural conservador para reescritas da mesma chamada.
2. Testar deslocamento, comentários, renomeações, múltiplas ocorrências, remoção
   parcial, alerta novo, substituição ambígua, parsing e timeout. Casos genuinamente
   ambíguos devem continuar null. Sem mapa confiável, não adivinhar a identidade.
3. Explicar a causa no registro/painel: separar ambiguidade de ocorrência, parsing,
   falha operacional e mudança de cobertura. Hoje `motivos_indeterminacao` recebe
   apenas `arquivos_inconclusivos`, portanto pode estar vazio mesmo com `ambiguos`.
4. Revisar associações e capacidades das regras em artefato separado. O perfil
   permanece congelado; qualquer mudança futura de regra exige novo perfil e
   reprodução/versionamento do baseline, não sobrescrita silenciosa.
5. Reavaliar os scans/bytes arquivados com v1/v2 em uma saída nova, sem LLM. Só
   depois realizar um replay de integração. Relatar concordâncias e divergências,
   não buscar artificialmente zero indeterminações.

O comparador, as regras, o catálogo e os prompts **não foram alterados nesta
avaliação**. O aceite da melhoria futura depende de associações corretas, inclusive
nos controles negativos, e de uma avaliação que não reutilize este conjunto como
se fosse um teste independente não inspecionado.

## Reproduzir e conferir

```bash
.venv/bin/python scripts/audit/evaluate_reference_fixes.py \
  --saida outputs/auditoria_sast/referencias_codefixes_NOVA

make test-unit PYTHON=.venv/bin/python
```

Escolha uma saída inexistente. A execução faz scans locais reais, sem serviços
LLM/Node e sem instalar dependências. Saídas parciais são identificadas; não são
sobrescritas. O procedimento de aplicação de trechos exige marcadores separados
em linhas próprias; limites ambíguos ficam para revisão manual.

Evidências: [inventário](../../outputs/auditoria_sast/referencias_codefixes_v1/inventario.json),
[resultados CSV](../../outputs/auditoria_sast/referencias_codefixes_v1/resultados.csv),
[resumo](../../outputs/auditoria_sast/referencias_codefixes_v1/resumo.json),
[manifesto e hashes](../../outputs/auditoria_sast/referencias_codefixes_v1/manifesto.json) e
[verificação histórica](../../outputs/auditoria_sast/referencias_codefixes_v1/verificacao.json).
As variantes guardam arquivo anterior/posterior, trecho de referência, diff,
scan bruto e comparação por ocorrência.

Passaram 215 testes unitários, incluindo quatro testes novos da montagem dos
arquivos e confinamento de caminhos. Foram conferidos 2.114 arquivos históricos,
sem alterações. O checkout usado foi mantido limpo no commit fixado. Não houve
commit/push ou execução da campanha LLM. Os hashes adicionais identificam o código
do comparador e as explicações pedagógicas consultadas.
